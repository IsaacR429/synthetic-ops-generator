import test from "node:test"
import assert from "node:assert/strict"

import type { SourceDomain } from "../src/types/api.ts"

test("frontend SourceDomain supports resilience", () => {
    const domain: SourceDomain = "resilience"

    assert.equal(domain, "resilience")
})
