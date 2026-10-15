import test from "node:test"
import assert from "node:assert/strict"

import type {
    GeneratedEvent,
} from "../src/types/api.ts"

test("frontend GeneratedEvent includes placement identity", () => {
    const event: GeneratedEvent = {
        event_id: "evt-001",
        event_type: "resilience.failover.completed",
        schema_version: "1.0",
        event_time: "2026-10-14T12:00:00Z",
        source_system: "streamops",
        source_domain: "resilience",
        scenario_id: "BANK-06",
        run_id: "RUN0000001",
        chg_id: null,
        business_stream: "payments",
        service: "payment-service",
        component: "payment-api",
        environment: "production",
        site_id: "primary-site",
        service_instance_id: "payment-api-primary",
        sequence_number: 1,
        synthetic: true,
        data: {},
    }

    assert.equal(
        event.site_id,
        "primary-site",
    )

    assert.equal(
        event.service_instance_id,
        "payment-api-primary",
    )
})
