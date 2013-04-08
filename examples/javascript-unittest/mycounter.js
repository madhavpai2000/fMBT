function mycounter(initial_value)
{
    this.value = initial_value

    this.inc = function () {
        this.value += 1
    }

    this.reset = function () {
        // Reset to zero in a not-that-funny way.
        // Let's see if any test can detect this bug.
        this.value = (this.value / this.value) - 1
    }

    this.count = function () {
        return this.value
    }
}
