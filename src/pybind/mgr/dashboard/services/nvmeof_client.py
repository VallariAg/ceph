# pylint: disable=unexpected-keyword-arg

import functools
import logging
from typing import Annotated, Any, Callable, Dict, Generator, List, \
    NamedTuple, Optional, Type, get_args, get_origin

from ..exceptions import DashboardException
from .nvmeof_conf import NvmeofGatewaysConfig, is_mtls_enabled

logger = logging.getLogger("nvmeof_client")

try:
    # if the protobuf version is newer than what we generated with
    # proto file import will fail (because of differences between what's
    # available in centos and ubuntu).
    # this "hack" should be removed once we update both the
    # distros; centos and ubuntu.
    import os
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

    import grpc  # type: ignore
    import grpc._channel  # type: ignore
    from google.protobuf.json_format import MessageToDict  # type: ignore
    from google.protobuf.message import Message  # type: ignore

    from .proto import gateway_pb2 as pb2  # type: ignore
    from .proto import gateway_pb2_grpc as pb2_grpc  # type: ignore
except ImportError:
    grpc = None
else:

    class NVMeoFClient(object):
        pb2 = pb2

        def __init__(self, gw_group: Optional[str] = None, server_address: Optional[str] = None):
            logger.info("Initiating nvmeof gateway connection...")
            try:
                if not gw_group:
                    res = NvmeofGatewaysConfig.get_service_info()
                else:
                    res = NvmeofGatewaysConfig.get_service_info(gw_group)
                if res is None:
                    raise DashboardException("Gateway group does not exist")
                service_name, self.gateway_addr = res
            except TypeError as e:
                raise DashboardException(
                    f'Unable to retrieve the gateway info: {e}'
                )

            # While creating listener need to direct request to the gateway
            # address where listener is supposed to be added.
            if server_address:
                gateways_info = NvmeofGatewaysConfig.get_gateways_config()
                matched_gateway = next(
                    (
                        gateway
                        for gateways in gateways_info['gateways'].values()
                        for gateway in gateways
                        if server_address in gateway['service_url']
                    ),
                    None
                )
                if matched_gateway:
                    self.gateway_addr = matched_gateway.get('service_url')
                    logger.debug("Gateway address set to: %s", self.gateway_addr)
            enable_auth = is_mtls_enabled(service_name)
            if enable_auth:
                client_key = NvmeofGatewaysConfig.get_client_key(service_name)
                client_cert = NvmeofGatewaysConfig.get_client_cert(service_name)
                server_cert = NvmeofGatewaysConfig.get_ssl_cert(service_name)
                logger.info('Securely connecting to: %s', self.gateway_addr)
                credentials = grpc.ssl_channel_credentials(
                    root_certificates=server_cert,
                    private_key=client_key,
                    certificate_chain=client_cert,
                )
                self.channel = grpc.secure_channel(self.gateway_addr, credentials)
            else:
                logger.info("Insecurely connecting to: %s", self.gateway_addr)
                self.channel = grpc.insecure_channel(self.gateway_addr)
            self.stub = pb2_grpc.GatewayStub(self.channel)

        def get_gateway_info(self):
            return self.stub.get_gateway_info(self.pb2.get_gateway_info_req())

        def get_gateway_stats(self):
            return self.stub.get_gateway_stats(self.pb2.get_gateway_stats_req())

        def get_gw_version(self):
            gw_info = self.get_gateway_info()
            return self.pb2.gw_version(status=gw_info.status,
                                       error_message=gw_info.error_message,
                                       version=gw_info.version)

        def get_gateway_log_level(self):
            return self.stub.get_gateway_log_level(self.pb2.get_gateway_log_level_req())

        def set_gateway_log_level(self, log_level):
            return self.stub.stub.set_gateway_log_level(
                self.pb2.set_gateway_log_level_req(log_level=log_level)
            )

        def show_gateway_listeners_info(self, nqn):
            return self.stub.show_gateway_listeners_info(
                self.pb2.show_gateway_listeners_info_req(subsystem_nqn=nqn)
            )

        def get_spdk_nvmf_log_flags_and_level(self, all_log_flags):
            return self.stub.get_spdk_nvmf_log_flags_and_level(
                self.pb2.get_spdk_nvmf_log_flags_and_level_req(all_log_flags=all_log_flags)
            )

        def set_spdk_nvmf_logs(self, log_level, print_level, extra_log_flags):
            return self.stub.set_spdk_nvmf_logs(
                self.pb2.set_spdk_nvmf_logs_req(log_level=log_level,
                                                print_level=print_level,
                                                extra_log_flags=extra_log_flags)
            )

        def disable_spdk_nvmf_logs(self, extra_log_flags):
            return self.stub.disable_spdk_nvmf_logs(
                self.pb2.disable_spdk_nvmf_logs_req(extra_log_flags=extra_log_flags)
            )

        def list_subsystems(self, nqn = None):
            if not nqn:
                return self.stub.list_subsystems(
                    self.pb2.list_subsystems_req(subsystem_nqn=nqn)
                )
            return self.stub.list_subsystems(
                self.pb2.list_subsystems_req()
            )

        def create_subsystem(self, subsystem_nqn, serial_number, max_namespaces, 
                             enable_ha, no_group_append, dhchap_key):
            return self.stub.create_subsystem(
                self.pb2.create_subsystem_req(
                    subsystem_nqn=subsystem_nqn,
                    serial_number=serial_number,
                    max_namespaces=max_namespaces,
                    enable_ha=enable_ha,
                    no_group_append=no_group_append,
                    dhchap_key=dhchap_key,
                )
            )

        def delete_subsystem(self, subsystem_nqn, force):
            return self.stub.delete_subsystem(
                NVMeoFClient.pb2.delete_subsystem_req(
                    subsystem_nqn=subsystem_nqn, force=force
                )
            )
        
        def change_subsystem_key(self, subsystem_nqn, dhchap_key):
            return self.stub.change_subsystem_key(
                self.pb2.change_subsystem_key_req(
                    subsystem_nqn=subsystem_nqn, dhchap_key=dhchap_key
                )
            )

        def get_subsystems(self):
            return self.stub.get_subsystems(
                self.pb2.get_subsystems_req()
            )
        # def

    Model = Dict[str, Any]
    Collection = List[Model]

    import errno

    NVMeoFError2HTTP = {
        # errno errors
        errno.EPERM: 403,  # 1
        errno.ENOENT: 404,  # 2
        errno.EACCES: 403,  # 13
        errno.EEXIST: 409,  # 17
        errno.ENODEV: 404,  # 19
        # JSONRPC Spec: https://www.jsonrpc.org/specification#error_object
        -32602: 422,  # Invalid Params
        -32603: 500,  # Internal Error
    }

    def handle_nvmeof_error(func: Callable[..., Message]) -> Callable[..., Message]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Message:
            try:
                response = func(*args, **kwargs)
            except grpc._channel._InactiveRpcError as e:  # pylint: disable=protected-access
                raise DashboardException(
                    msg=e.details(),
                    code=e.code(),
                    http_status_code=504,
                    component="nvmeof",
                )

            status = getattr(response, "status", None)
            error_message = getattr(response, "error_message", None)

            if status not in (None, 0):
                raise DashboardException(
                    msg=error_message or "NVMeoF operation failed",
                    code=status,
                    http_status_code=NVMeoFError2HTTP.get(status, 400),  # type: ignore[arg-type]
                    component="nvmeof",
                )
            return response

        return wrapper

    def empty_response(func: Callable[..., Message]) -> Callable[..., None]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> None:
            func(*args, **kwargs)

        return wrapper

    class MaxRecursionDepthError(Exception):
        pass

    def _convert(value, field_type, depth, max_depth) -> Generator:
        if depth > max_depth:
            raise MaxRecursionDepthError(
                f"Maximum nesting depth of {max_depth} exceeded at depth {depth}.")

        if isinstance(value, dict) and hasattr(field_type, '_fields'):
            # Lazily create NamedTuple for nested dicts
            yield from _lazily_create_namedtuple(value, field_type, depth + 1, max_depth)
        elif isinstance(value, list):
            # Handle empty lists directly
            if not value:
                yield []
            else:
                # Lazily process each item in the list based on the expected item type
                item_type = field_type.__args__[0] if hasattr(field_type, '__args__') else None
                processed_items = []
                for v in value:
                    if item_type:
                        processed_items.append(next(_convert(v, item_type,
                                                             depth + 1, max_depth), None))
                    else:
                        processed_items.append(v)
                yield processed_items
        else:
            # Yield the value as is for simple types
            yield value

    def _lazily_create_namedtuple(data: Any, target_type: Type[NamedTuple],
                                  depth: int, max_depth: int) -> Generator:
        # pylint: disable=protected-access
        """ Lazily create NamedTuple from a dict """
        field_values = {}
        for field, field_type in zip(target_type._fields,
                                     target_type.__annotations__.values()):
            if get_origin(field_type) == Annotated:
                field_type = get_args(field_type)[0]
            # these conditions are complex since we need to navigate between dicts,
            # empty dicts and objects
            if isinstance(data, dict) and data.get(field) is not None:
                try:
                    field_values[field] = next(_convert(data.get(field), field_type,
                                                        depth, max_depth), None)
                except StopIteration:
                    return
            elif hasattr(data, field):
                try:
                    field_values[field] = next(_convert(getattr(data, field), field_type,
                                                        depth, max_depth), None)
                except StopIteration:
                    return
            else:
                field_values[field] = target_type._field_defaults.get(field)

        namedtuple_instance = target_type(**field_values)  # type: ignore
        yield namedtuple_instance

    def obj_to_namedtuple(data: Any, target_type: Type[NamedTuple],
                          max_depth: int = 7) -> NamedTuple:
        """
        Convert an object or dict to a NamedTuple, handling nesting and lists lazily.
        This will raise an error if nesting depth exceeds the max depth (default 4)
        to avoid bloating the memory in case of mutual references between objects.

        :param data: The input data - object or dictionary
        :param target_type: The target NamedTuple type
        :param max_depth: The maximum depth allowed for recursion
        :return: An instance of the target NamedTuple with fields populated from the JSON
        """

        if not isinstance(target_type, type) or not hasattr(target_type, '_fields'):
            raise TypeError("target_type must be a NamedTuple type.")
        if isinstance(data, list):
            raise TypeError("data can't be a list.")
        if data is None:
            raise TypeError("data can't be None.")
        namedtuple_values = next(_lazily_create_namedtuple(data, target_type, 1, max_depth))
        return namedtuple_values

    def namedtuple_to_dict(obj):
        if isinstance(obj, tuple) and hasattr(obj, '_asdict'):
            # If it's a namedtuple, convert it to a dictionary
            return {k: namedtuple_to_dict(v) for k, v in obj._asdict().items()}
        if isinstance(obj, list):
            # If it's a list, check each item and convert if it's a namedtuple
            return [
                namedtuple_to_dict(item)
                if isinstance(item, tuple) and hasattr(item, '_asdict')
                else item
                for item in obj
            ]
        return obj

    def convert_to_model(model: Type[NamedTuple],
                         finalize: Optional[Callable[[Dict], Dict]] = None
                         ) -> Callable[..., Callable[..., Model]]:
        def decorator(func: Callable[..., Message]) -> Callable[..., Model]:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Model:
                message = func(*args, **kwargs)
                msg_dict = MessageToDict(message, including_default_value_fields=True,
                                         preserving_proto_field_name=True)  # type: ignore

                result = namedtuple_to_dict(obj_to_namedtuple(msg_dict, model))
                if finalize:
                    return finalize(result)
                return result

            return wrapper

        return decorator

    # pylint: disable-next=redefined-outer-name
    def pick(field: str, first: bool = False,
             ) -> Callable[..., Callable[..., object]]:
        def decorator(func: Callable[..., Dict]) -> Callable[..., object]:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> object:
                model = func(*args, **kwargs)
                field_to_ret = model[field]
                if first:
                    field_to_ret = field_to_ret[0]
                return field_to_ret
            return wrapper
        return decorator
