import test from "node:test"
import assert from "node:assert/strict"

import {
    SOURCE_DOMAIN_OPTIONS,
    formatSourceDomain,
} from "../src/types/sourceDomainPresentation.ts"

test("source-domain presentation includes resilience", () => {
    const resilience = SOURCE_DOMAIN_OPTIONS.find(
        (option) => option.value === "resilience",
    )

    assert.deepEqual(resilience, {
        value: "resilience",
        label: "Resilience",
    })

    assert.equal(
        formatSourceDomain("resilience"),
        "Resilience",
    )
})
