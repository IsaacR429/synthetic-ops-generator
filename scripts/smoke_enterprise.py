from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)


def main() -> None:
    bank = load_enterprise_configuration("config/enterprises/bank_alpha")
    print(f"Loaded Enterprise: {bank.name} ({bank.enterprise_id})")
    print(f"  Industry: {bank.industry}")
    print(f"  Business Streams: {len(bank.business_streams)}")
    print(f"  Services: {len(bank.services)}")
    print(f"  Components: {len(bank.components)}")
    print(f"  Sites: {len(bank.sites)}")
    print(f"  Service Instances: {len(bank.service_instances)}")
    print(f"  Dependencies: {len(bank.dependencies)}")

    insurer = load_enterprise_configuration("config/enterprises/insurer_alpha")
    print(f"\nLoaded Enterprise: {insurer.name} ({insurer.enterprise_id})")
    print(f"  Industry: {insurer.industry}")
    print(f"  Business Streams: {len(insurer.business_streams)}")
    print(f"  Services: {len(insurer.services)}")
    print(f"  Components: {len(insurer.components)}")
    print(f"  Sites: {len(insurer.sites)}")
    print(f"  Service Instances: {len(insurer.service_instances)}")
    print(f"  Dependencies: {len(insurer.dependencies)}")


if __name__ == "__main__":
    main()
