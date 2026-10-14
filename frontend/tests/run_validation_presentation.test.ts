import test from "node:test"
import assert from "node:assert/strict"

import {
    EXECUTION_VALIDATION_LABEL,
    formatExecutionValidation,
} from "../src/types/runValidationPresentation.ts"

test("run validation is presented as execution validation", () => {
    assert.equal(
        EXECUTION_VALIDATION_LABEL,
        "Execution Validation",
    )
})

test("execution validation preserves existing status semantics", () => {
    assert.equal(
        formatExecutionValidation(null, true),
        "Pending",
    )

    assert.equal(
        formatExecutionValidation(null, false),
        "Not reported",
    )

    assert.equal(
        formatExecutionValidation(true, false),
        "Passed",
    )

    assert.equal(
        formatExecutionValidation(false, false),
        "Failed",
    )
})
