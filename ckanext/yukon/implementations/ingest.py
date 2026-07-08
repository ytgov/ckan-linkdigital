from __future__ import annotations

from typing_extensions import override

from ckanext.ingest.interfaces import IIngest
from ckanext.ingest.shared import ExtractionStrategy

from ckanext.yukon import ingest


class Ingest(IIngest):
    @override
    def get_ingest_strategies(self) -> dict[str, type[ExtractionStrategy]]:
        return {
            "yukon:organization": ingest.YukonOrganizationStrategy,
            "yukon:topic": ingest.YukonTopicStrategy,
            "yukon:package": ingest.YukonPackageStrategy,
            "yukon:resource": ingest.YukonResourceStrategy,
        }
