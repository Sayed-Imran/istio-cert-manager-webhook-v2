class AnnotationDoesNotExist(Exception):
    """Exception raised when an annotation does not exist."""

    pass


class InvalidAnnotationValue(Exception):
    """Exception raised when an annotation value is invalid."""

    pass


class IssuerDoesnotExist(Exception):
    """Exception raised when an issuer does not exist."""

    pass


class ClusterIssuerDoesnotExist(Exception):
    """Exception raised when a cluster issuer does not exist."""

    pass

class GatewayAlreadyExists(Exception):
    """Exception raised when a gateway already exists."""
    pass

class IstioGatewayNamespaceError(Exception):
    """Exception raised when there is an error with the Istio gateway namespace."""
    pass
