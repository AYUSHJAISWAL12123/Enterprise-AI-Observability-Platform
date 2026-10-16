"""Evaluator CronJob entrypoint."""

import asyncio
import sys

from obs_core.config import Settings
from obs_core.logging import configure_logging

from evaluator._bq import BigQueryReader, BigQueryWriter
from evaluator._config import EvaluatorSettings
from evaluator._vertex import VertexEvaluator
from evaluator.worker import run_batch


async def _main() -> None:
    settings = Settings()
    eval_settings = EvaluatorSettings()

    configure_logging(
        log_level=settings.log_level.value,
        service_name=settings.service_name,
        environment=settings.environment.value,
    )

    reader = BigQueryReader(
        project_id=settings.gcp_project_id,
        dataset_raw=settings.bq_dataset_raw,
        table_raw=settings.bq_table_events,
        dataset_metrics=eval_settings.bq_dataset_metrics,
        table_metrics=eval_settings.bq_table_evals,
    )
    writer = BigQueryWriter(
        project_id=settings.gcp_project_id,
        dataset_metrics=eval_settings.bq_dataset_metrics,
        table_metrics=eval_settings.bq_table_evals,
    )
    vertex = VertexEvaluator(
        project_id=settings.gcp_project_id,
        location=settings.gcp_region,
        judge_model=eval_settings.vertex_judge_model,
        embedding_model=eval_settings.vertex_embedding_model,
    )

    try:
        await run_batch(
            reader=reader,
            writer=writer,
            vertex=vertex,
            batch_size=eval_settings.eval_batch_size,
        )
    except Exception:
        # Crash the CronJob pod so Kubernetes registers it as Failed.
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_main())
