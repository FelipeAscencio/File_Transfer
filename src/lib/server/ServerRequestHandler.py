from dataclasses import dataclass, field
import heapq
from io import BufferedRandom
import logging
from lib.utils.types import REQUEST
from lib.utils.constants import OPERATION, BUFSIZE
from lib.utils.types import ADDR
import os
from lib.packages.InitPackage import InitPackage
from lib.utils.enums import PackageType
from lib.utils.logger import create_logger
from lib.utils.Socket import Socket
from lib.packages.AckPackage import AckPackage
from lib.packages.DataPackage import DataPackage
from lib.packages.FinPackage import FinPackage
from lib.protocols.selective_repeat import SelectiveRepeatProtocol
from typing import Optional, IO, Union
from lib.utils.enums import Protocol
from lib.packages.NackPackage import NackPackage


@dataclass
class ClientInfo:
    addr: ADDR
    operation: OPERATION
    last_package_type: PackageType
    filename: str
    protocol: SelectiveRepeatProtocol
    file: BufferedRandom | None = None
    seq_number: int = 0
    heap: list[DataPackage] = field(default_factory=list)  # = []
    retries: dict[int, int] = field(default_factory=dict)  # = {seq_num: retries_left}
    first_window_sent: bool = False


class ServerRequestHandler:
    """
    Handles server requests and responses.
    """

    def __init__(
        self, server_storage: str, socket: Socket, protocol, logging_level=logging.DEBUG
    ) -> None:
        self.clients: dict[str, ClientInfo] = {}
        # self.retrys = 0
        self.server_storage = server_storage
        self.socket = socket
        self.logger = create_logger(
            "request-handler", "[REQUEST HANDLER]", logging_level
        )
        self.protocol = protocol

    def handle_request(self, request: REQUEST):
        # self.logger.info(f"Handling request: {request}")
        package, addr = request

        if not package.valid:  ## que sea solo para checksum
            self.logger.warning(f"Invalid package received: {package}")
            return self.send_nack(addr, package.sequence_number)

        addr_str = f"{addr[0]}:{addr[1]}"
        if addr_str not in self.clients:
            if not isinstance(package, InitPackage):
                self.logger.error(
                    f"Received unexpected package from {addr_str}: {package}"
                )
                return

            if self.protocol == Protocol.STOP_WAIT:
                _window_size = 1
            else:
                _window_size = 5

            protocol_handle = SelectiveRepeatProtocol(
                socket=self.socket,
                server_addr=addr,
                window_size=_window_size,
                logging_level=self.logger.level,
            )

            full_path = os.path.join(self.server_storage, package.file_name)
            if package.operation == "download" and not os.path.exists(full_path):
                self.logger.error(
                    f"Archivo no existe: {package.file_name} en {self.server_storage}"
                )
                self.send_fin(addr)
                return

            self.clients[addr_str] = ClientInfo(
                addr=addr,
                operation=package.operation,
                last_package_type=PackageType.INIT,
                filename=package.file_name,
                protocol=protocol_handle,
            )
            self.logger.info(
                f"New client connected: {addr_str} with operation {package.operation}"
            )

        client_info = self.clients[addr_str]

        if isinstance(package, InitPackage):
            self.send_init_response(client_info)
        elif isinstance(package, DataPackage):
            self.handle_upload_request(package, client_info)
        elif isinstance(package, NackPackage):
            if client_info.operation == "download":
                try:
                    self.handle_download_request(package, client_info)
                except TimeoutError:
                    self.handle_finish_request(client_info)
            else:
                self.logger.info(
                    "[REQUEST HANDLER] Unexpected ACK during upload (ignored)"
                )
        elif isinstance(package, AckPackage):
            if client_info.operation == "download":
                try:
                    self.handle_download_request(package, client_info)
                except TimeoutError:
                    self.handle_finish_request(client_info)
            else:
                self.logger.info(
                    "[REQUEST HANDLER] Unexpected ACK during upload (ignored)"
                )
        elif isinstance(package, FinPackage):
            self.handle_finish_request(client_info)
        else:
            self.logger.error(
                f"Unknown package type for client {addr_str}: {client_info.last_package_type}"
            )

    def handle_upload_request(self, package: DataPackage, client_info: ClientInfo):
        if not package.valid:
            self.send_nack(client_info.addr, int(package.sequence_number))
            return

        if client_info.file is None:
            file = open(f"{self.server_storage}/{client_info.filename}", "ab+")
            client_info.file = file
        else:
            file = client_info.file

        self.logger.debug(f"pack seq : {package.sequence_number}")
        self.logger.debug(f"client seq_num : {client_info.seq_number}")

        if package.sequence_number == client_info.seq_number:
            file.write(package.data)
            client_info.seq_number = self.obtener_proximo_seq_number(client_info)
            self.logger.debug(f"client seq_num Actualizado: {client_info.seq_number}")
            heapq.heapify(client_info.heap)
            while client_info.heap:
                if client_info.heap[0].sequence_number == client_info.seq_number:
                    item = heapq.heappop(client_info.heap)
                    file.write(item.data)
                    client_info.seq_number = self.obtener_proximo_seq_number(
                        client_info
                    )
                else:
                    break
        else:
            client_info.heap.append(package)

        self.logger.debug(f"File written successfully from {client_info.addr}")

        self.send_ack(client_info.addr, int(package.sequence_number))

    def obtener_proximo_seq_number(self, client_info: ClientInfo) -> int:
        if self.protocol == Protocol.SELECTIVE_REPEAT:
            return client_info.seq_number + 1
        else:
            return client_info.seq_number ^ 1

    def handle_download_request(
        self, package: Union[AckPackage, NackPackage], client_info: ClientInfo
    ):
        if self.protocol.value == Protocol.STOP_WAIT.value:
            self.handle_download_request_stopnwait(package, client_info)
        elif self.protocol.value == Protocol.SELECTIVE_REPEAT.value:
            if not client_info.first_window_sent:
                client_info.first_window_sent = True
                self._send_first_window(client_info)
                return

            self.handle_download_request_selectiverepeat(package, client_info)
        else:
            self.logger.error(f"Unknown protocol: {self.protocol}")

    def handle_download_request_stopnwait(
        self, package: Union[AckPackage, NackPackage], client_info: ClientInfo
    ):
        # Llego a max retries, cerramos todo
        if client_info.retries.get(package.sequence_number, 0) >= 10:
            self.logger.error(
                f"Max retries reached for {client_info.addr}, closing connection"
            )
            self.send_fin(client_info.addr)
            client_info.retries.pop(package.sequence_number)
            return

        next_seq_number = package.sequence_number

        # Es un ACK, entonces saco el retries, ya no se necesita
        if isinstance(package, AckPackage):
            client_info.retries.pop(package.sequence_number, None)
            if client_info.file is None:
                try:
                    file = open(f"{self.server_storage}/{client_info.filename}", "rb+")
                    client_info.file = file
                except FileNotFoundError:
                    self.logger.error(
                        f"File not found: {client_info.filename} for {client_info.addr}"
                    )
                    self.send_fin(client_info.addr)
                    return

            else:
                file = client_info.file

            chunk = file.read(BUFSIZE - 50)
            if not chunk:
                self.logger.info(f"File transfer finished for {client_info.addr}")
                self.send_fin(client_info.addr)
                return
            self.last_chunk = chunk
            next_seq_number = self.obtener_proximo_seq_number(client_info)
            client_info.protocol.sequence_number = next_seq_number
            client_info.seq_number = next_seq_number

        # Si es un NACK, entonces reintentamos el paquete
        elif isinstance(package, NackPackage):
            self.logger.debug(
                f"reintentando paquete,try {client_info.retries.get(package.sequence_number, 0)}"
            )
            chunk = self.last_chunk
            client_info.retries[package.sequence_number] = (
                client_info.retries.get(package.sequence_number, 0) + 1
            )
        data_package = DataPackage(chunk, next_seq_number)
        self.socket.sendto(data_package, client_info.addr)

    def send_init_response(self, client_info: ClientInfo):
        self.send_ack(client_info.addr)

    def handle_finish_request(self, client_info: ClientInfo):
        self.logger.info(f"File transfer finished from {client_info.addr}")
        self.send_ack(client_info.addr)

        if client_info.file:
            client_info.file.close()
            client_info.file = None

        del self.clients[f"{client_info.addr[0]}:{client_info.addr[1]}"]

    def send_ack(self, addr: ADDR, seq_num: int = 0):
        ack_package = AckPackage(seq_num)
        self.socket.sendto(ack_package, addr)
        # self.logger.info(f"ACK sent to {addr} with seq_num {seq_num}")

    def send_nack(self, addr: ADDR, seq_num: int = 0):
        nack_package = NackPackage(seq_num)
        self.socket.sendto(nack_package, addr)
        self.logger.info(f"NACK sent to {addr}")

    def send_fin(self, addr: ADDR):
        fin_package = FinPackage()
        self.socket.sendto(fin_package, addr)
        self.logger.info(f"FIN sent to {addr}")

    # ---------------------------- SELECTIVE REPEAT  ---------------------------- #
    def handle_download_request_selectiverepeat(
        self, package: Union[AckPackage, NackPackage], client_info: ClientInfo
    ) -> None:
        file = self._get_file_open(client_info)
        if file is None:
            return

        self.logger.debug(
            f"Recibiendo ACK: {package.sequence_number}  - ({client_info.protocol.window.see_top_seq_num()} {client_info.protocol.window.see_last_seq_num()})"
        )

        if isinstance(package, NackPackage):
            self.logger.debug(f"Llego un NAK con seq_num {package.sequence_number}")
            if not client_info.protocol.resend_package(package.sequence_number):
                self.send_fin(client_info.addr)
            return

        # se chequea si ack esta dentro de la ventana, si no se ignora
        # ventana se avanza si el ack es el primero
        if not client_info.protocol.ack_received(package.sequence_number):
            self.logger.debug(
                f"ACK/NACK {package.sequence_number} fuera de ventana: ({client_info.protocol.first_sequence_number} {client_info.protocol.last_sequence_number})"
            )
            return

        # si ACK no es valido (NAK), hay que reenviar
        if not package.valid:
            self.logger.warning(f"Llego un NAK: {package}")
            if not client_info.protocol.resend_package(package.sequence_number):
                self.send_fin(client_info.addr)
            return

        # si el ack no es el primero de la ventana, no avanzo ventana pero mando chunk
        if not client_info.protocol.window.see_top_seq_num() > package.sequence_number:
            self.logger.debug(
                f"Llego ACK {package.sequence_number} antes que ACK {client_info.protocol.window.see_top_seq_num()}"
            )

        file = self._get_file_open(client_info)
        if file is None:
            return

        chunk = file.read(BUFSIZE - 50)
        if not chunk:
            self.logger.info(f"File transfer finished for {client_info.addr}")
            self.send_fin(client_info.addr)
            return

        client_info.protocol.send_chunk(chunk)

        #### FALTA BUFFEREAR EN CASO DE TIMEOUT ####
        #### FALTA CHEQUEAR QUE LA VNTANA NO ESTA LLENA ####

    def _get_file_open(self, client_info: ClientInfo) -> Optional[IO[bytes]]:
        if client_info.file is None:
            try:
                file = open(f"{self.server_storage}/{client_info.filename}", "rb+")
                client_info.file = file
            except FileNotFoundError:
                self.logger.error(
                    f"File not found: {client_info.filename} for {client_info.addr}"
                )
                self.send_fin(client_info.addr)
                return None
        return client_info.file

    ### por ahora los mandamos, y asumimos que llegan
    def _send_first_window(self, client_info: ClientInfo) -> None:
        file = self._get_file_open(client_info)
        if file is None:
            return

        for i in range(client_info.protocol.window.size):
            chunk = file.read(BUFSIZE - 50)
            if not chunk:
                self.logger.info(f"File transfer finished for {client_info.addr}")
                self.send_fin(client_info.addr)
                return

            client_info.protocol.send_chunk(chunk)
        client_info.first_window_sent = True
