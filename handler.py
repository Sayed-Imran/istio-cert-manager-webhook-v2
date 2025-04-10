import logging

from config import CertificateConfig
from errors import AnnotationDoesNotExist, GatewayAlreadyExists, IstioGatewayNamespaceError
from kubernetes_utility import KubernetesUtility
from schemas import CertificateSchema, GatewayOwnerReferenceSchema, VirtualServiceOwnerReferenceSchema

kubernetes_utility = KubernetesUtility()

class IstioHandler:
    def __init__(self, request_object: dict):

        self.request_object = request_object
        self.kubernetes_utility = kubernetes_utility
        self.certificate_data = {}
        self.gateway_data = {}

    def preflight_check(self):
        self._check_gateway_exists()
        self._handle_annotations()

    def create_certificate(self):
        try:
            if self.gateway_data == {}:
                logging.error("Gateway data is empty, hence skipping certificate creation")
                return
            gateway_metadata = self.gateway_data["metadata"]
            gateway_spec = self.gateway_data["spec"]
            owner_reference = GatewayOwnerReferenceSchema(
                name=gateway_metadata["name"], uid=gateway_metadata["uid"]
            )
            certificate = CertificateSchema(
                namespace=gateway_metadata["namespace"],
                name=gateway_spec["servers"][0]["tls"]["credentialName"],
                dns_names=gateway_spec["servers"][0]["hosts"],
                duration=self.certificate_data["duration"],
                renew_before=self.certificate_data["renew_before"],
                issuer_name=self.certificate_data["issuer_name"],
                issuer_kind=self.certificate_data["issuer_kind"],
                secret_name=gateway_spec["servers"][0]["tls"]["credentialName"],
            )
            if self.kubernetes_utility.get_certificate(
                certificate.name, certificate.namespace
            ):
                self.kubernetes_utility.update_certificate(certificate, owner_reference)
                logging.info(
                    f"Certificate {certificate.name} already exists, updating it"
                )
            else:
                self.kubernetes_utility.create_certificate(certificate, owner_reference)
                logging.info(f"Certificate {certificate.name} created successfully")
        except AnnotationDoesNotExist as e:
            logging.info(
                f"Annotation does not exist, hence skipping certificate creation"
            )
        except Exception as e:
            raise e

    def create_gateway(self):
        try:
            if self.kubernetes_utility.get_istio_gateway(
                self.request_object["spec"]["gateways"][0].split("/")[-1], "istio-system"
            ):
                self.kubernetes_utility.update_istio_gateway(
                    self.request_object["spec"]["gateways"][0].split("/")[-1],
                    "istio-system",
                    {"vs": f"{self.request_object['metadata']['namespace']}/{self.request_object['metadata']['name']}"},
                    self.request_object["spec"]["hosts"],
                    f"{self.request_object['metadata']['name']}-tls",
                )
            else:
                self.gateway_data = self.kubernetes_utility.create_istio_gateway(
                        f"{self.request_object['spec']['gateways'][0].split('/')[-1]}",
                        "istio-system",
                        {"vs": f"{self.request_object['metadata']['namespace']}/{self.request_object['metadata']['name']}"},
                        self.request_object["spec"]["hosts"],
                        f"{self.request_object['metadata']['name']}-tls"
                    )

            logging.info(
                f"Gateway {self.request_object['spec']['gateways'][0]} created successfully"
            )

        except GatewayAlreadyExists as e:
            logging.error(
                f"Gateway {self.request_object['spec']['gateways'][0]} already exists"
            )
            raise e
        except Exception as e:
            logging.error(f"Error creating gateway: {e}")
            raise e

    def _handle_annotations(self):
        gateway_annotations = self.request_object["metadata"]["annotations"]
        issuer = gateway_annotations.get("cert-manager.io/issuer")
        cluster_issuer = gateway_annotations.get("cert-manager.io/cluster-issuer")

        if issuer:
            logging.info(f"Using Issuer: {issuer}")
            self.certificate_data["issuer_name"] = issuer
            self.certificate_data["issuer_kind"] = "Issuer"
            self.kubernetes_utility.get_issuer(
                issuer, self.request_object["metadata"]["namespace"]
            )
        elif cluster_issuer:
            logging.info(f"Using ClusterIssuer: {cluster_issuer}")
            self.certificate_data["issuer_name"] = cluster_issuer
            self.certificate_data["issuer_kind"] = "ClusterIssuer"
            self.kubernetes_utility.get_cluster_issuer(cluster_issuer)
        else:
            raise AnnotationDoesNotExist(
                "Gateway must have either 'cert-manager.io/issuer' or 'cert-manager.io/cluster-issuer' annotation"
            )
        self.certificate_data["duration"] = gateway_annotations.get(
            "cert-manager.io/duration", CertificateConfig.duration
        )
        self.certificate_data["renew_before"] = gateway_annotations.get(
            "cert-manager.io/renew-before", CertificateConfig.renew_before
        )


    def _check_gateway_exists(self):
        """
        Check if an Istio Gateway exists and validate its ownership.
        Raises appropriate exceptions for invalid gateway configurations.
        """
        if not self.request_object.get("spec", {}).get("gateways"):
            logging.error("No gateways specified in the request")
            raise IstioGatewayNamespaceError("No gateways specified in the request")
        
        gateway_reference = self.request_object["spec"]["gateways"][0]
        if not isinstance(gateway_reference, str) or not gateway_reference.startswith("istio-system/"):
            logging.error("Gateway needs to be in the istio-system namespace")
            raise IstioGatewayNamespaceError("Gateway must be in the istio-system namespace")
        
        gateway_name = gateway_reference.split("/")[-1]
        
        gateway_data = self.kubernetes_utility.get_istio_gateway(gateway_name, "istio-system")
        if not gateway_data:
            logging.info(f"Gateway {gateway_name} does not exist")
            return
        
        annotations = gateway_data.get("metadata", {}).get("annotations", {})
        vs_details = annotations.get("vs", "")
        
        current_vs_name = self.request_object.get("metadata", {}).get("name", "")
        current_vs_namespace = self.request_object.get("metadata", {}).get("namespace", "")
        
        try:
            vs_namespace, vs_name = vs_details.split("/", 1)
            if vs_name == current_vs_name and vs_namespace == current_vs_namespace:
                logging.info(f"Gateway {gateway_name} already exists and is owned by the same VirtualService")
                return
        except ValueError:
            # Invalid vs annotation format - treat as unowned
            pass
            
        # Gateway exists but is not owned by this VirtualService
        logging.error(f"Gateway {gateway_name} already exists")
        raise GatewayAlreadyExists(f"Gateway {gateway_name} already exists")

    def delete_gateway(self):
        try:
            gateway_name = self.request_object["spec"]["gateways"][0].split("/")[-1]
            logging.info(
                f"Deleting Gateway {gateway_name}"
            )
            self.kubernetes_utility.delete_istio_gateway(
                gateway_name, "istio-system"
            )
            logging.info(f"Gateway {gateway_name} deleted successfully")
        except Exception as e:
            logging.error(f"Error deleting gateway: {e}")
