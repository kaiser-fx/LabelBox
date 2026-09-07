# Import all rule modules so their @register_rule decorators execute at import time
import app.rules.mrp_rules  # noqa: F401
import app.rules.net_quantity_rules  # noqa: F401
import app.rules.manufacturer_rules  # noqa: F401
import app.rules.date_rules  # noqa: F401
import app.rules.consumer_care_rules  # noqa: F401
