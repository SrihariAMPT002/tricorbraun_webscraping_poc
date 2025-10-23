def uom_to_ml(uom, value):
    """
    Convert a value with optional unit to milliliters.
    Supports: oz (ounces), ml (milliliters), gallon/gal, dram.
    If no unit is provided (numeric-only), assumes ounces for backward compatibility.
    Returns a float rounded to 2 decimal places, or None on parse error.
    """
    if value is None:
        return None

    # Try to extract number and optional unit (accepts variants like 'fl oz', 'gal', 'ml', 'dram')
    # m = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*(ml|milliliter|millilitre|milli|fl oz|floz|oz|ounce|ounces|gallon|gal|gallons|dram|drams)?\.?$", uom)

    # Normalize unit strings
    unit = uom.lower().replace(".", "").strip()
    num = float(value)
    if unit in ("ml", "milliliter", "millilitre", "milli"):
        ml_value = num
    if unit in ("cc", "CC"):
        ml_value = num
    elif unit in ("oz", "fl oz", "floz", "ounce", "ounces"):
        ml_value = num * 29.5735
    elif unit in ("gallon", "gal", "gallons"):
        # US gallon to ml
        ml_value = num * 3785.411784
    elif unit in ("dram", "drams"):
        # US fluid dram to ml
        ml_value = num * 3.6966911953125
    else:
        return None

    return round(ml_value, 2)
