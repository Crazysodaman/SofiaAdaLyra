"""OPS contribution to the message matrix."""
import re

from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


_OPERATIONAL = re.compile(
    r"\b(?:service|services|daemon|process|processes|container|containers|"
    r"docker|system|server|servers|host|hosts|node|nodes|fleet|endpoint|"
    r"endpoints|deploy|deploys|deployment|deployments|package|packages|"
    r"install|uninstall|update|upgrade|patch|reboot|restart|boot|backup|"
    r"restore|maintenance|machine|virtual\s+machine|vm|portainer|"
    r"home\s+assistant|jmri|hyper-?v|ollama|telemetry|remote)\b",
    re.IGNORECASE,
)


class OpsMatrixEvaluator:
    domain = MatrixDomain.OPS

    def evaluate(self, envelope, turn):
        if turn.intent is MatrixIntent.OPERATIONAL_QUERY:
            return DomainContribution(
                self.domain,
                MatrixRelevance.RELEVANT,
                "operational query may require OPS evidence",
            )
        if (
            turn.intent is MatrixIntent.ACTION_REQUEST
            and _OPERATIONAL.search(envelope.content)
        ):
            return DomainContribution(
                self.domain,
                MatrixRelevance.RELEVANT,
                "operational action may require OPS planning or evidence",
            )
        return None