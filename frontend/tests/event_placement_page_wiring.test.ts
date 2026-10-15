import test from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const eventInspectionPage = readFileSync(
    "src/pages/EventInspectionPage.tsx",
    "utf8",
)

test("event inspection surfaces placement identity", () => {
    assert.match(
        eventInspectionPage,
        /event\.site_id/,
    )

    assert.match(
        eventInspectionPage,
        /event\.service_instance_id/,
    )

    assert.match(
        eventInspectionPage,
        />\s*Site\s*</,
    )

    assert.match(
        eventInspectionPage,
        />\s*Service Instance\s*</,
    )
})
