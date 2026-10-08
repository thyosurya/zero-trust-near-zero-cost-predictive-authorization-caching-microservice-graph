# control-plane/pdp/policies/authz.rego
package authz

import future.keywords.if
import future.keywords.in

# Default tolak semua — tidak ada allow tanpa aturan eksplisit
default allow := false

# Izinkan jika ada entri eksplisit
allow if {
    some rule in data.service_rules
    rule.source == input.source_identity
    rule.target == input.target_identity
    input.action in rule.allowed_actions
}

# Sensitivity level untuk kandidat cache
# (digunakan Cache Distributor saat query OPA untuk dapat sensitivity)
sensitivity := level if {
    some rule in data.service_rules
    rule.source == input.source_identity
    rule.target == input.target_identity
    level := rule.sensitivity
}

default sensitivity := "medium"
