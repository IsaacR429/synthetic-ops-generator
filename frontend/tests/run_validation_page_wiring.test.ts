import test from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const runDetailPage = readFileSync(
    "src/pages/RunDetailPage.tsx",
    "utf8",
)

const runConfigurationPage = readFileSync(
    "src/pages/RunConfigurationPage.tsx",
    "utf8",
)

test("run detail uses execution-validation presentation", () => {
    assert.match(
        runDetailPage,
        /EXECUTION_VALIDATION_LABEL/,
    )

    assert.match(
        runDetailPage,
        /formatExecutionValidation\(/,
    )
})

test("run configuration uses execution-validation presentation", () => {
    assert.match(
        runConfigurationPage,
        /EXECUTION_VALIDATION_LABEL/,
    )

    assert.match(
        runConfigurationPage,
        /formatExecutionValidation\(/,
    )
})
