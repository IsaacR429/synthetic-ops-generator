from synthetic_ops_generator.domain.enums import SourceDomain


CONTINUOUS_SUPPORTED_SOURCES: frozenset[SourceDomain] = frozenset(
    {
        SourceDomain.METRIC,
        SourceDomain.LOG,
        SourceDomain.INFRASTRUCTURE_TEST,
    }
)


def supports_continuous_execution(
    source: SourceDomain,
) -> bool:
    return source in CONTINUOUS_SUPPORTED_SOURCES
