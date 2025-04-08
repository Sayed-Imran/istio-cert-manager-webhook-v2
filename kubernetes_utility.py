import logging

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from errors import ClusterIssuerDoesnotExist, IssuerDoesnotExist, GatewayAlreadyExists
from schemas import CertificateSchema, GatewayOwnerReferenceSchema, VirtualServiceOwnerReferenceSchema


class KubernetesUtility:
    def __init__(self):
        config.load_config()
        self.client = client.CustomObjectsApi()

    def get_certificate(self, name, namespace):
        try:
            return self.client.get_namespaced_custom_object(
                "cert-manager.io",
                "v1",
                namespace,
                "certificates",
                name,
            )
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    def create_certificate(
        self, certificate: CertificateSchema, owner_reference: GatewayOwnerReferenceSchema
    ):
        certificate_body = {
            "apiVersion": "cert-manager.io/v1",
            "kind": "Certificate",
            "metadata": {
                "name": certificate.name,
                "ownerReferences": [owner_reference.model_dump()],
            },
            "spec": {
                "secretName": certificate.secret_name,
                "duration": certificate.duration,
                "renewBefore": certificate.renew_before,
                "dnsNames": certificate.dns_names,
                "usages": [
                    "digital signature",
                    "key encipherment",
                ],
                "issuerRef": {
                    "name": certificate.issuer_name,
                    "kind": certificate.issuer_kind,
                    "group": "cert-manager.io",
                },
            },
        }
        self.client.create_namespaced_custom_object(
            "cert-manager.io",
            "v1",
            certificate.namespace,
            "certificates",
            certificate_body,
        )

    def update_certificate(
        self, certificate: CertificateSchema, owner_reference: GatewayOwnerReferenceSchema
    ):
        certificate_data = {
            "apiVersion": "cert-manager.io/v1",
            "kind": "Certificate",
            "metadata": {
                "name": certificate.name,
                "ownerReferences": [owner_reference.model_dump()],
            },
            "spec": {
                "secretName": certificate.secret_name,
                "duration": certificate.duration,
                "renewBefore": certificate.renew_before,
                "dnsNames": certificate.dns_names,
                "usages": [
                    "digital signature",
                    "key encipherment",
                ],
                "issuerRef": {
                    "name": certificate.issuer_name,
                    "kind": certificate.issuer_kind,
                    "group": "cert-manager.io",
                },
            },
        }
        self.client.replace_namespaced_custom_object(
            "cert-manager.io",
            "v1",
            certificate.namespace,
            "certificates",
            certificate.name,
            certificate_data,
        )

    def get_issuer(self, name, namespace):
        try:
            return self.client.get_namespaced_custom_object(
                "cert-manager.io",
                "v1",
                namespace,
                "issuers",
                name,
            )
        except ApiException as e:
            logging.error(f"Error fetching issuer: {e}")
            if e.status == 404:
                raise IssuerDoesnotExist(
                    f"Issuer {name} does not exist in namespace {namespace}"
                )

    def get_cluster_issuer(self, name):
        try:
            return self.client.get_cluster_custom_object(
                "cert-manager.io",
                "v1",
                "clusterissuers",
                name,
            )
        except ApiException as e:
            logging.error(f"Error fetching cluster issuer: {e}")
            if e.status == 404:
                raise ClusterIssuerDoesnotExist(f"ClusterIssuer {name} does not exist")


    def get_istio_gateway(self, name, namespace):
        try:
            return self.client.get_namespaced_custom_object(
                "networking.istio.io",
                "v1",
                namespace,
                "gateways",
                name,
            )
        except ApiException as e:
            logging.error(f"Error fetching Istio Gateway: {e}")
            if e.status == 404:
                return None
            raise


    def create_istio_gateway(self, name: str, namespace:str, hosts: list[str], credential_name: str ,owner_reference: VirtualServiceOwnerReferenceSchema):
        gateway = {
            "apiVersion": "networking.istio.io/v1",
            "kind": "Gateway",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "ownerReferences": [owner_reference.model_dump()],
            },
            "spec": {
                "selector": {
                    "istio": "ingressgateway",
                },
                "servers": [
                    {
                        "port": {
                            "number": 443,
                            "name": "https",
                            "protocol": "HTTPS",
                        },
                        "tls": {
                            "mode": "SIMPLE",
                            "credentialName": credential_name,
                        },
                        "hosts": hosts,
                    }
                ]
            }
        }

        try:
            return self.client.create_namespaced_custom_object(
                "networking.istio.io",
                "v1",
                namespace,
                "gateways",
                gateway,
            )
        except ApiException as e:
            logging.error(f"Error creating Istio Gateway: {e}")
            if e.status == 409:
                logging.error(f"Istio Gateway {name} already exists.")
                raise GatewayAlreadyExists(
                    f"Istio Gateway {name} already exists"
                )
            else:
                raise
