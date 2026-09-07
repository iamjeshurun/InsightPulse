"""Optional Hugging Face fine-tuning entry point for a single task.

The imports are intentionally lazy so baseline users do not need the GPU stack.
"""

from __future__ import annotations

import argparse
import json
import platform
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sklearn

from .baseline import SUPPORTED_TASKS
from .evaluation import evaluate_task
from .io import read_jsonl


def _labeled(records: list[dict[str, Any]], task: str) -> list[dict[str, str]]:
    return [{"text": str(row["text"]), "label": str(row[task])} for row in records if row.get(task)]


def train_transformer(
    data_dir: Path,
    output_dir: Path,
    task: str,
    model_name: str,
    epochs: float,
    seed: int,
    max_length: int = 128,
    train_batch_size: int = 32,
    class_weighted: bool = False,
    learning_rate: float = 2e-5,
    tokenizer_name: str | None = None,
) -> dict[str, Any]:
    try:
        import numpy as np
        import torch
        from datasets import Dataset, DatasetDict
        from sklearn.metrics import accuracy_score, f1_score
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            DataCollatorWithPadding,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise SystemExit("Install transformer dependencies with: pip install -e '.[transformer]'") from exc

    rows = {
        split: _labeled(read_jsonl(data_dir / f"{split}.jsonl"), task)
        for split in ("train", "validation", "test")
    }
    labels = sorted({row["label"] for row in rows["train"]})
    label_to_id = {label: index for index, label in enumerate(labels)}
    datasets = DatasetDict(
        {
            split: Dataset.from_list(
                [{"text": row["text"], "label": label_to_id[row["label"]]} for row in values]
            )
            for split, values in rows.items()
        }
    )
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name or model_name)
    tokenized = datasets.map(
        lambda batch: tokenizer(batch["text"], truncation=True, max_length=max_length), batched=True
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=len(labels),
        id2label={index: label for label, index in label_to_id.items()},
        label2id=label_to_id,
    )

    def metrics(evaluation: Any) -> dict[str, float]:
        predictions = np.argmax(evaluation.predictions, axis=-1)
        return {
            "accuracy": float(accuracy_score(evaluation.label_ids, predictions)),
            "macro_f1": float(f1_score(evaluation.label_ids, predictions, average="macro")),
        }

    counts = Counter(row["label"] for row in rows["train"])
    weights = torch.tensor(
        [(len(rows["train"]) / (len(labels) * counts[label])) ** 0.5 for label in labels],
        dtype=torch.float32,
    )

    class WeightedTrainer(Trainer):
        def compute_loss(
            self, model: Any, inputs: dict[str, Any], return_outputs: bool = False,
            num_items_in_batch: Any = None,
        ) -> Any:
            gold = inputs.pop("labels")
            outputs = model(**inputs)
            loss_weights = weights.to(outputs.logits.device) if class_weighted else None
            loss = torch.nn.functional.cross_entropy(outputs.logits, gold, weight=loss_weights)
            return (loss, outputs) if return_outputs else loss

    arguments = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=epochs,
        learning_rate=learning_rate,
        per_device_train_batch_size=train_batch_size,
        per_device_eval_batch_size=train_batch_size * 2,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        seed=seed,
        report_to="none",
        save_total_limit=1,
        logging_steps=50,
    )
    trainer = WeightedTrainer(
        model=model,
        args=arguments,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        processing_class=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=metrics,
    )
    trainer.train()
    test_output = trainer.predict(tokenized["test"], metric_key_prefix="test")
    probabilities = torch.softmax(torch.tensor(test_output.predictions), dim=-1).numpy()
    predictions: list[dict[str, dict[str, Any]]] = []
    for row in probabilities:
        best = int(np.argmax(row))
        predictions.append(
            {
                task: {
                    "label": labels[best],
                    "confidence": float(row[best]),
                    "probabilities": {label: float(row[index]) for index, label in enumerate(labels)},
                }
            }
        )
    evaluation = evaluate_task(
        read_jsonl(data_dir / "test.jsonl"), predictions, task
    )
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "task": task,
        "model_name": model_name,
        "split_sizes": {split: len(values) for split, values in rows.items()},
        "test": evaluation,
        "trainer_metrics": {key: float(value) for key, value in test_output.metrics.items()},
        "training": {
            "epochs": epochs,
            "seed": seed,
            "max_length": max_length,
            "train_batch_size": train_batch_size,
            "class_weighted": class_weighted,
            "learning_rate": learning_rate,
            "tokenizer_name": tokenizer_name or model_name,
            "class_weights": {label: float(weights[index]) for index, label in enumerate(labels)},
        },
        "reproducibility": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "torch": torch.__version__,
        },
    }
    best_dir = output_dir / "best_model"
    trainer.save_model(best_dir)
    tokenizer.save_pretrained(best_dir)
    (output_dir / "evaluation_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output_dir / "test_predictions.jsonl").open("w", encoding="utf-8") as handle:
        for source, prediction in zip(read_jsonl(data_dir / "test.jsonl"), predictions):
            handle.write(json.dumps({"id": source["id"], "labels": prediction}, sort_keys=True) + "\n")
    (output_dir / "model_card.md").write_text(
        f"# Model Card: {task.title()} Transformer\n\n"
        f"Fine-tuned `{model_name}` on {report['split_sizes']['train']:,} examples. "
        f"Held-out accuracy: {evaluation['accuracy']:.4f}; macro-F1: {evaluation['macro_f1']:.4f}.\n\n"
        "See `evaluation_report.json` for per-class metrics, calibration, slices, and errors. "
        "This benchmark is domain-specific and requires human review in consequential use.\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune a transformer for one InsightPulse task")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--task", required=True, choices=SUPPORTED_TASKS)
    parser.add_argument("--model-name", default="distilroberta-base")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--train-batch-size", type=int, default=32)
    parser.add_argument("--class-weighted", action="store_true")
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--tokenizer-name")
    args = parser.parse_args()
    report = train_transformer(
        args.data_dir, args.output_dir, args.task, args.model_name, args.epochs, args.seed,
        args.max_length, args.train_batch_size, args.class_weighted, args.learning_rate,
        args.tokenizer_name,
    )
    print(json.dumps({"task": args.task, "accuracy": report["test"]["accuracy"], "macro_f1": report["test"]["macro_f1"]}, indent=2))


if __name__ == "__main__":
    main()
