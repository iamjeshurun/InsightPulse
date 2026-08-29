"""Optional Hugging Face fine-tuning entry point for a single task.

The imports are intentionally lazy so baseline users do not need the GPU stack.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .baseline import SUPPORTED_TASKS
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
) -> None:
    try:
        import numpy as np
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
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenized = datasets.map(lambda batch: tokenizer(batch["text"], truncation=True), batched=True)
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

    arguments = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=epochs,
        learning_rate=2e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        seed=seed,
        report_to="none",
    )
    trainer = Trainer(
        model=model,
        args=arguments,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        processing_class=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=metrics,
    )
    trainer.train()
    test_metrics = trainer.evaluate(tokenized["test"], metric_key_prefix="test")
    best_dir = output_dir / "best_model"
    trainer.save_model(best_dir)
    tokenizer.save_pretrained(best_dir)
    (output_dir / "test_metrics.json").write_text(
        json.dumps(test_metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune a transformer for one InsightPulse task")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--task", required=True, choices=SUPPORTED_TASKS)
    parser.add_argument("--model-name", default="distilroberta-base")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    train_transformer(args.data_dir, args.output_dir, args.task, args.model_name, args.epochs, args.seed)


if __name__ == "__main__":
    main()
