# Risk Management Skill
Validates trades against SEBI rules and personal risk limits.

## Tools
- `validate_risk(symbol, quantity, price, side)`: Hard-gate validation for every trade.
- `get_risk_summary()`: Summary of daily loss, position limits, and OPS.
