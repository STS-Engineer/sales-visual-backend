import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.client import Client
from app.models.monthly_report import MonthlyReport
from app.models.visual import Visual

EXPECTED_CLIENT_NAMES = [
    "Sales NIDEC",
    "Sales Inteva",
    "Sales DY",
    "Sales MAHLE",
    "Sales Valeo",
    "Sales First Brand",
    "Sales JE",
    "Sales BOSCH",
    "Sales Lucas",
    "Sales B&D",
]


@dataclass
class MigrationPlan:
    visuals_total: int
    expected_clients: list[str]
    clients_existing: int
    clients_to_create: list[str]
    report_candidates: int
    reports_existing: int
    reports_to_create: int
    skipped_unexpected_client: int
    skipped_missing_created_at: int
    skipped_duplicate_period: int
    unexpected_client_names: list[str]


def _report_period(visual: Visual) -> tuple[int, int] | None:
    source_date = visual.end_date or visual.created_at
    if not source_date:
        return None
    return source_date.year, source_date.month


async def build_migration_plan(session: AsyncSession) -> MigrationPlan:
    try:
        existing_clients_result = await session.execute(select(Client))
        existing_clients = {
            client.name: client
            for client in existing_clients_result.scalars().all()
        }
    except (ProgrammingError, DBAPIError):
        await session.rollback()
        existing_clients = {}

    try:
        existing_reports_result = await session.execute(select(MonthlyReport))
        existing_report_keys = {
            (report.client_id, report.report_year, report.report_month)
            for report in existing_reports_result.scalars().all()
        }
    except (ProgrammingError, DBAPIError):
        await session.rollback()
        existing_report_keys = set()

    result = await session.execute(select(Visual).order_by(Visual.id))
    visuals = list(result.scalars().all())

    expected_names = set(EXPECTED_CLIENT_NAMES)
    seen_report_keys: set[tuple[str, int, int]] = set()
    report_candidates = 0
    reports_existing = 0
    reports_to_create = 0
    skipped_unexpected_client = 0
    skipped_missing_created_at = 0
    skipped_duplicate_period = 0
    unexpected_names: set[str] = set()

    for visual in visuals:
        if visual.name not in expected_names:
            skipped_unexpected_client += 1
            unexpected_names.add(visual.name)
            continue

        period = _report_period(visual)
        if period is None:
            skipped_missing_created_at += 1
            continue

        report_candidates += 1
        report_key = (visual.name, period[0], period[1])

        client = existing_clients.get(visual.name)
        if client and (client.id, period[0], period[1]) in existing_report_keys:
            reports_existing += 1
            continue

        if report_key in seen_report_keys:
            skipped_duplicate_period += 1
            continue

        seen_report_keys.add(report_key)
        reports_to_create += 1

    return MigrationPlan(
        visuals_total=len(visuals),
        expected_clients=EXPECTED_CLIENT_NAMES,
        clients_existing=sum(1 for name in EXPECTED_CLIENT_NAMES if name in existing_clients),
        clients_to_create=[
            name
            for name in EXPECTED_CLIENT_NAMES
            if name not in existing_clients
        ],
        report_candidates=report_candidates,
        reports_existing=reports_existing,
        reports_to_create=reports_to_create,
        skipped_unexpected_client=skipped_unexpected_client,
        skipped_missing_created_at=skipped_missing_created_at,
        skipped_duplicate_period=skipped_duplicate_period,
        unexpected_client_names=sorted(unexpected_names),
    )


def print_migration_plan(plan: MigrationPlan) -> None:
    print("MIGRATION_DRY_RUN")
    print(f"visuals_total={plan.visuals_total}")
    print(f"expected_clients={len(plan.expected_clients)}")
    print(f"clients_existing={plan.clients_existing}")
    print(f"clients_to_create={len(plan.clients_to_create)}")
    for name in plan.clients_to_create:
        print(f"client_to_create={name}")
    print(f"report_candidates={plan.report_candidates}")
    print(f"reports_existing={plan.reports_existing}")
    print(f"reports_to_create={plan.reports_to_create}")
    print(f"skipped_unexpected_client={plan.skipped_unexpected_client}")
    print(f"skipped_missing_created_at={plan.skipped_missing_created_at}")
    print(f"skipped_duplicate_period={plan.skipped_duplicate_period}")
    for name in plan.unexpected_client_names:
        print(f"unexpected_client_name={name}")


async def apply_migration(session: AsyncSession) -> dict[str, int]:
    result = await session.execute(select(Visual).order_by(Visual.id))
    visuals = list(result.scalars().all())

    existing_clients_result = await session.execute(select(Client))
    clients_by_name = {
        client.name: client
        for client in existing_clients_result.scalars().all()
    }

    created_clients = 0
    for name in EXPECTED_CLIENT_NAMES:
        if name in clients_by_name:
            continue

        source_visual = next((visual for visual in visuals if visual.name == name), None)
        client = Client(
            name=name,
            power_bi_url=source_visual.power_bi_url if source_visual else None,
            power_bi_label=None,
            vp_sales_name=source_visual.vp_sales if source_visual else None,
            person_name="AH",
            is_active=True,
        )
        session.add(client)
        clients_by_name[name] = client
        created_clients += 1

    await session.flush()

    existing_reports_result = await session.execute(select(MonthlyReport))
    existing_report_keys = {
        (report.client_id, report.report_year, report.report_month)
        for report in existing_reports_result.scalars().all()
    }

    seen_report_keys: set[tuple[int, int, int]] = set()
    created_reports = 0
    skipped_reports = 0

    for visual in visuals:
        client = clients_by_name.get(visual.name)
        if not client:
            skipped_reports += 1
            continue

        period = _report_period(visual)
        if period is None:
            skipped_reports += 1
            continue

        report_key = (client.id, period[0], period[1])
        if report_key in existing_report_keys or report_key in seen_report_keys:
            skipped_reports += 1
            continue

        seen_report_keys.add(report_key)
        status = "done" if visual.status == "Done" else "waiting"
        now = datetime.now(tz=visual.created_at.tzinfo)
        session.add(
            MonthlyReport(
                client_id=client.id,
                monday_item_id=visual.monday_item_id,
                report_year=period[0],
                report_month=period[1],
                statut=status,
                end_date=visual.end_date,
                fichier_url=visual.file_url,
                marked_done_at=now if status == "done" else None,
                notification_sent=status == "done",
                notification_sent_at=now if status == "done" else None,
            )
        )
        created_reports += 1

    await session.commit()

    return {
        "created_clients": created_clients,
        "created_reports": created_reports,
        "skipped_reports": skipped_reports,
    }


async def main(apply: bool) -> None:
    async with AsyncSessionLocal() as session:
        plan = await build_migration_plan(session)
        print_migration_plan(plan)
        if apply:
            result = await apply_migration(session)
            print("MIGRATION_APPLIED")
            for key, value in result.items():
                print(f"{key}={value}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
