from synthetic_ops_generator.checks.models import (
    CheckApplicability,
    CheckDefinition,
    CheckExecutionSpec,
)
from synthetic_ops_generator.domain.enums import (
    AssetClass,
    ServiceClass,
)
from synthetic_ops_generator.domain.operational_test import (
    TestCategory,
)


APPLICATION_FUNCTIONAL_VALIDATION = CheckDefinition(
    check_definition_id="application.functional_validation",
    category=TestCategory.APPLICATION,
    test_type="functional_validation",
    name="Service functional validation",
    description=(
        "Validate that the business-facing service performs its "
        "intended functional behaviour."
    ),
    applicability=CheckApplicability(
        service_classes={
            ServiceClass.BUSINESS_APPLICATION,
            ServiceClass.BUSINESS_SERVICE,
        },
    ),
)


APPLICATION_TRANSACTION_PROCESSING = CheckDefinition(
    check_definition_id="application.transaction_processing",
    category=TestCategory.APPLICATION,
    test_type="transaction_processing",
    name="Service transaction processing validation",
    description=(
        "Validate representative end-to-end business transaction "
        "processing for an applicable business service."
    ),
    applicability=CheckApplicability(
        service_classes={
            ServiceClass.BUSINESS_APPLICATION,
            ServiceClass.BUSINESS_SERVICE,
        },
    ),
)


APPLICATION_POST_DEPLOYMENT_SMOKE = CheckDefinition(
    check_definition_id="application.post_deployment_smoke",
    category=TestCategory.APPLICATION,
    test_type="post_deployment_smoke",
    name="Post-deployment smoke validation",
    description=(
        "Perform lightweight functional validation of a deployed "
        "business application before broader assurance."
    ),
    applicability=CheckApplicability(
        service_classes={
            ServiceClass.BUSINESS_APPLICATION,
        },
    ),
)


INFRASTRUCTURE_CONNECTIVITY = CheckDefinition(
    check_definition_id="infrastructure.connectivity",
    category=TestCategory.INFRASTRUCTURE,
    test_type="connectivity",
    name="Service connectivity validation",
    description=(
        "Validate expected network or protocol reachability for "
        "addressable infrastructure assets."
    ),
    applicability=CheckApplicability(
        asset_classes={
            AssetClass.DATABASE,
            AssetClass.MIDDLEWARE,
            AssetClass.LINUX,
            AssetClass.WINDOWS,
            AssetClass.MAINFRAME,
            AssetClass.NETWORK,
            AssetClass.DIGITAL_INFRASTRUCTURE,
        },
    ),
)


INFRASTRUCTURE_SERVICE_HEALTH = CheckDefinition(
    check_definition_id="infrastructure.service_health",
    category=TestCategory.INFRASTRUCTURE,
    test_type="service_health",
    name="Service health validation",
    description=(
        "Validate the operational health or readiness of an "
        "infrastructure service or control surface."
    ),
    applicability=CheckApplicability(
        asset_classes={
            AssetClass.DATABASE,
            AssetClass.MIDDLEWARE,
            AssetClass.LINUX,
            AssetClass.WINDOWS,
            AssetClass.MAINFRAME,
            AssetClass.NETWORK,
            AssetClass.DIGITAL_INFRASTRUCTURE,
            AssetClass.INFORMATION_SECURITY,
        },
    ),
)


INFRASTRUCTURE_DEPENDENCY_CONNECTIVITY = CheckDefinition(
    check_definition_id="infrastructure.dependency_connectivity",
    category=TestCategory.INFRASTRUCTURE,
    test_type="dependency_connectivity",
    name="Dependency connectivity validation",
    description=(
        "Validate that an applicable service can reach or interact "
        "with an expected dependency. The concrete dependency is "
        "resolved from enterprise topology rather than encoded in "
        "the reusable definition."
    ),
    applicability=CheckApplicability(
        service_classes={
            ServiceClass.BUSINESS_APPLICATION,
            ServiceClass.BUSINESS_SERVICE,
            ServiceClass.INFRASTRUCTURE_SERVICE,
        },
    ),
)


DEFAULT_APPLICATION_CHECKS = (
    CheckExecutionSpec(
        definition=APPLICATION_FUNCTIONAL_VALIDATION,
        mandatory=True,
    ),
    CheckExecutionSpec(
        definition=APPLICATION_TRANSACTION_PROCESSING,
        mandatory=True,
    ),
    CheckExecutionSpec(
        definition=APPLICATION_POST_DEPLOYMENT_SMOKE,
        mandatory=True,
    ),
)


DEFAULT_INFRASTRUCTURE_CHECKS = (
    CheckExecutionSpec(
        definition=INFRASTRUCTURE_CONNECTIVITY,
        mandatory=True,
    ),
    CheckExecutionSpec(
        definition=INFRASTRUCTURE_SERVICE_HEALTH,
        mandatory=True,
    ),
    CheckExecutionSpec(
        definition=INFRASTRUCTURE_DEPENDENCY_CONNECTIVITY,
        mandatory=True,
    ),
)
