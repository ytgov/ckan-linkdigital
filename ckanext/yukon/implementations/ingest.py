from __future__ import annotations

import ckan.plugins as p

from ckanext.ingest.interfaces import IIngest
from ckanext.ingest.shared import ExtractionStrategy

from ckanext.yukon import ingest


class Ingest(p.SingletonPlugin):
    p.implements(IIngest)

    def get_ingest_strategies(self) -> dict[str, type[ExtractionStrategy]]:
        return {
            "yukon:organization": ingest.YukonOrganizationStrategy,
            "yukon:topic": ingest.YukonTopicStrategy,
            "yukon:package": ingest.YukonPackageStrategy,
            "yukon:resource": ingest.YukonResourceStrategy,
        }
