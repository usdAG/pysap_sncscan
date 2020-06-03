# ===========
# pysap - Python library for crafting SAP's network protocols packets
#
# SECUREAUTH LABS. Copyright (C) 2020 SecureAuth Corporation. All rights reserved.
#
# The library was designed and developed by Martin Gallo from
# the SecureAuth Labs team.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# ==============

# Standard imports
import ssl
import socket
import struct
# External imports
from cryptography.hazmat.backends import default_backend
from scapy.layers.inet import TCP
from scapy.packet import Packet, bind_layers
from scapy.supersocket import SSLStreamSocket
from scapy.fields import (ByteField, ConditionalField, EnumField, FieldLenField,
                          IntField, PacketListField, SignedByteField, LongField, PadField,
                          LEIntField, LESignedIntField, StrFixedLenField, ShortField)
# Custom imports
from pysap.SAPRouter import SAPRoutedStreamSocket
from pysap.utils.crypto import SCRAM_SHA256, SCRAM_PBKDF2SHA256
from pysap.utils.fields import (PacketNoPadded, AdjustableFieldLenField, LESignedByteField,
                                LESignedShortField, LESignedLongField)


hdb_segmentkind_values = {
    0: "Invalid",
    1: "Request",
    2: "Reply",
    5: "Error",
}
"""SAP HDB Segment Kind Values"""


hdb_message_type_values = {
    0: "NIL",
    2: "EXECUTEDIRECT",
    3: "PREPARE",
    4: "ABAPSTREAM",
    5: "XA_START",
    6: "XA_JOIN",
    7: "XA_COMMIT",
    13: "EXECUTE",
    16: "READLOB",
    17: "WRITELOB",
    18: "FINDLOB",
    25: "PING",
    65: "AUTHENTICATE",
    66: "CONNECT",
    67: "COMMIT",
    68: "ROLLBACK",
    69: "CLOSERESULTSET",
    70: "DROPSTATEMENTID",
    71: "FETCHNEXT",
    72: "FETCHABSOLUTE",
    73: "FETCHRELATIVE",
    74: "FETCHFIRST",
    75: "FETCHLAST",
    77: "DISCONNECT",
    78: "EXECUTEITAB",
    79: "FETCHNEXTITAB",
    80: "INSERTNEXTITAB",
    81: "BATCHPREPARE",
    82: "DBCONNECTINFO",
    83: "XOPEN_XASTART",
    84: "XOPEN_XAEND",
    85: "XOPEN_XAPREPARE",
    86: "XOPEN_XACOMMIT",
    87: "XOPEN_XAROLLBACK",
    88: "XOPEN_XARECOVER",
    89: "XOPEN_XAFORGET",
}
"""SAP HDB Segment Message Type Values"""


hdb_function_code_values = {
    0: "NIL",
    1: "DDL",
    2: "INSERT",
    3: "UPDATE",
    4: "DELETE",
    5: "SELECT",
    6: "SELECTFORUPDATE",
    7: "EXPLAIN",
    8: "DBPROCEDURECALL",
    9: "DBPROCEDURECALLWITHRESULT",
    10: "FETCH",
    11: "COMMIT",
    12: "ROLLBACK",
    13: "SAVEPOINT",
    14: "CONNECT",
    15: "WRITELOB",
    16: "READLOB",
    17: "PING",
    18: "DISCONNECT",
    19: "CLOSECURSOR",
    20: "FINDLOB",
    21: "ABAPSTREAM",
    22: "XASTART",
    23: "XAJOIN",
    24: "ITABWRITE",
    25: "XOPEN_XACONTROL",
    26: "XOPEN_XAPREPARE",
    27: "XOPEN_XARECOVER",
}
"""SAP HDB Segment Function Code Values"""


hdb_partkind_values = {
    0: "NIL",
    3: "COMMAND",
    5: "RESULTSET",
    6: "ERROR",
    10: "STATEMENTID",
    11: "TRANSACTIONID",
    12: "ROWSAFFECTED",
    13: "RESULTSETID",
    15: "TOPOLOGYINFORMATION",
    16: "TABLELOCATION",
    17: "READLOBREQUEST",
    18: "READLOBREPLY",
    25: "ABAPISTREAM",
    26: "ABAPOSTREAM",
    27: "COMMANDINFO",
    28: "WRITELOBREQUEST",
    29: "CLIENTCONTEXT",
    30: "WRITELOBREPLY",
    32: "PARAMETERS",
    33: "AUTHENTICATION",
    34: "SESSIONCONTEXT",
    35: "CLIENTID",
    38: "PROFILE",
    39: "STATEMENTCONTEXT",
    40: "PARTITIONINFORMATION",
    41: "OUTPUTPARAMETERS",
    42: "CONNECTOPTIONS",
    43: "COMMITOPTIONS",
    44: "FETCHOPTIONS",
    45: "FETCHSIZE",
    47: "PARAMETERMETADATA",
    48: "RESULTSETMETADATA",
    49: "FINDLOBREQUEST",
    50: "FINDLOBREPLY",
    51: "ITABSHM",
    53: "ITABCHUNKMETADATA",
    55: "ITABMETADATA",
    56: "ITABRESULTCHUNK",
    57: "CLIENTINFO",
    58: "STREAMDATA",
    59: "OSTREAMRESULT",
    60: "FDAREQUESTMETADATA",
    61: "FDAREPLYMETADATA",
    62: "BATCHPREPARE",
    63: "BATCHEXECUTE",
    64: "TRANSACTIONFLAGS",
    65: "ROWSLOTIMAGEPARAMMETADATA",
    66: "ROWSLOTIMAGERESULTSET",
    67: "DBCONNECTINFO",
    68: "LOBFLAGS",
    69: "RESULTSETOPTIONS",
    70: "XATRANSACTIONINFO",
    71: "SESSIONVARIABLE",
    72: "WORKLOADREPLAYCONTEXT",
    73: "SQLREPLYOTIONS",
}
"""SAP HDB Part Kind Values"""


def hdb_segment_is_request(segment):
    """Returns if the segment is a request

    :param segment: segment to look at
    :type segment: :class:`SAPHDBSegment`

    :return: if the segment is a request
    :rtype: ``bool``
    """
    return segment.segmentkind == 1


def hdb_segment_is_reply(segment):
    """Returns if the segment is a reply

    :param segment: segment to look at
    :type segment: :class:`SAPHDBSegment`

    :return: if the segment is a reply
    :rtype: ``bool``
    """
    return segment.segmentkind == 2


class SAPHDBPartAuthenticationField(PacketNoPadded):
    """SAP HANA SQL Command Network Protocol Authentication Part Field

    This packet represents a field in the Authentication Part
    """
    name = "SAP HANA SQL Command Network Protocol Authentication Field"
    fields_desc = [
        AdjustableFieldLenField("length", None, length_of="value"),
        StrFixedLenField("value", None, length_from=lambda pkt: pkt.length),
    ]


class SAPHDBPartAuthentication(PacketNoPadded):
    """SAP HANA SQL Command Network Protocol Authentication Part

    This packet represents an Authentication Part. The Authentication part consists of a count value and then
    a number of key/value pairs expressed with field values.

    Authentication methods documented are:
        - "GSS" - Provides GSS/Kerberos authentication.
        - "PLAINPASSWORD" - Reserved. Do not use.
        - "SAML" - Provides SAML authentication.
        - "SCRAMMD5" - Reserved. Do not use.
        - "SCRAMSHA256" - Provides password-based authentication.

    Non-documented methods are:
        - "JWT"
        - "SAPLogon"
        - "SCRAMPBKDF2SHA256"
        - "SessionCookie"
        - "X509Internal"

    Known authentication key values are:

    - GSS Authentication:
        - USERNAME - User name
        - METHODNAME - Method name
        - CLIENTCHALLENGE - Client challenge
            - KRB5OID - KRB5 object ID
            - TYPEOID - Type object ID
            - CLIENTGSSNAME - Client GSS Name
        - SERVERTOKEN - Server-specific Kerberos tokens
        - CLIENTOKEN - Client-specific Kerberos tokens
    - LDAP Authentication:
        - USERNAME - User name
        - METHODNAME - Method name ("LDAP")
        - CLIENTCHALLENGE - Client challenge
        - SERVERCHALLENGE - Server Challenge
            - CLIENTNONCE - Specifies the client nonce that was sent in the initial request.
            - SERVERNONCE - Specifies the server nonce.
            - SERVERPUBLICKEY - Specifies the server public key.
            - CAPABILITYRESULT - Specifies the capability, chosen by the server, from the client request.
        - CLIENTPROOF - Specifies the client proof.
            - ENCRYPTEDSESSKEY - Specifies the encrypted session key. This is specified as: RSAEncrypt(public key, SESSIONKEY + SERVERNONCE).
            - ENCRYPTEDPASSWORD - Specifies the encrypted password. This is specified as: AES256Encrypt(SESSIONKEY, PASSWORD + SERVERNONCE).
        - SERVERPROOF - Specifies the authentication result from the LDAP server. This is specified as either SUCCESS or FAIL.
    - SAML Authentication:
        - USERNAME - Specifies the user name (always empty user name).
        - METHODNAME - Specifies the method name.
        - SAMLASSERTION - Specifies the SAML assertion.
        - SAMLUSER - Specifies the user name associated with the SAML assertion.
        - FINALDATA - Specifies the final data (this is empty).
        - SESSIONCOOKIE - Specifies the session cookie used for the reconnect.
    - SCRAMSHA256 Authentication:
        - USERNAME - Specifies the user name.
        - METHODNAME - Specifies the method name.
        - CLIENTCHALLENGE - Specifies the client challenge. (64 bytes)
        - SERVERCHALLENGEDATA - Specifies the server challenge.
            - SALT - Specifies the password salt.
            - SERVERCHALLENGE - Specifies the server challenge.
        - CLIENTPROOF - Specifies the client proof. (35 bytes)
            - SCRAMMESSAGE - Specifies the SCRAM HMAC message, the actual Client Proof that is sent to the server. (32 bytes)
        - SERVERPROOF - Specifies the server proof.
    - Session Cookie Authentication:
        - USERNAME - Specifies the user name.
        - METHODNAME - Specifies the method name.
        - SESSIONCOOKIE - Specifies the session cookie, process ID, and hostname.
        - SERVERREPLY - Specifies the server reply (this is empty).
        - FINALDATA - Specifies the final data (this is empty).
    """
    name = "SAP HANA SQL Command Network Protocol Authentication Part"
    fields_desc = [
        FieldLenField("count", None, count_of="auth_fields", fmt="<H"),
        PacketListField("auth_fields", None, SAPHDBPartAuthenticationField, count_from=lambda x: x.count),
    ]


class SAPHDBPart(PacketNoPadded):
    """SAP HANA SQL Command Network Protocol Part

    This packet represents a part within a HDB packet.

    The part header is comprised of 16 bytes.
    """
    name = "SAP HANA SQL Command Network Protocol Part"
    fields_desc = [
        EnumField("partkind", 0, hdb_partkind_values, fmt="<b"),
        LESignedByteField("partattributes", 0),
        LESignedShortField("argumentcount", 0),
        LESignedIntField("bigargumentcount", 0),
        FieldLenField("bufferlength", None, length_of="buffer", fmt="<i"),
        LESignedIntField("buffersize", 2**17 - 32 - 24),
        PadField(PacketListField("buffer", None), 8),
    ]


class SAPHDBSegment(PacketNoPadded):
    """SAP HANA SQL Command Network Protocol Segment

    This packet represents a segment within a HDB packet.

    The segment header is comprised of 24 byte, being the first 13 bytes always the same fields and the remaining 11
    bytes depend on the segment kind field.
    """
    name = "SAP HANA SQL Command Network Protocol Segment"
    fields_desc = [
        # Segment length needs to be calculated counting the segment header
        FieldLenField("segmentlength", None, length_of="parts", fmt="<i", adjust=lambda x, l:l+24),
        LESignedIntField("segmentofs", 0),
        FieldLenField("noofparts", None, count_of="parts", fmt="<h"),
        LESignedShortField("segmentno", 1),
        EnumField("segmentkind", 1, hdb_segmentkind_values, fmt="<b"),
        ConditionalField(EnumField("messagetype", 0, hdb_message_type_values, fmt="<b"), hdb_segment_is_request),
        ConditionalField(LESignedByteField("commit", 0), hdb_segment_is_request),
        ConditionalField(LESignedByteField("commandoptions", 0), hdb_segment_is_request),
        ConditionalField(LongField("reserved1", 0), hdb_segment_is_request),
        ConditionalField(ByteField("reserved2", 0), hdb_segment_is_reply),
        ConditionalField(EnumField("functioncode", 0, hdb_function_code_values, fmt="<h"), hdb_segment_is_reply),
        ConditionalField(LongField("reserved3", 0), hdb_segment_is_reply),
        ConditionalField(StrFixedLenField("reserved4", None, 11), lambda pkt: not (hdb_segment_is_reply(pkt) or hdb_segment_is_request(pkt))),
        PacketListField("parts", None, SAPHDBPart, count_from=lambda x: x.noofparts),
    ]


class SAPHDB(Packet):
    """SAP HANA SQL Command Network Protocol packet

    This packet is used for the HANA SQL Command Network Protocol.

    The message header is comprised of 32 bytes.
    """
    name = "SAP HANA SQL Command Network Protocol"
    fields_desc = [
        LESignedLongField("sessionid", -1),
        LESignedIntField("packetcount", 0),
        FieldLenField("varpartlength", None, length_of="segments", fmt="<I"),
        LEIntField("varpartsize", 2**17 - 32),
        FieldLenField("noofsegm", None, count_of="segments", fmt="<h"),
        SignedByteField("packetoptions", 0),
        ByteField("reserved1", None),
        LEIntField("compressionvarpartlength", 0),
        IntField("reserved2", None),
        PacketListField("segments", None, SAPHDBSegment, count_from=lambda x: x.noofsegm),
    ]


class SAPHDBInitializationRequest(Packet):
    """SAP HANA SQL Command Network Protocol Initialization Request packet

    This packet is used for the HANA SQL Command Network Protocol during initialization.
    """
    name = "SAP HANA SQL Command Network Protocol Initialization Request"
    fields_desc = [
        StrFixedLenField("initialization", "\xff\xff\xff\xff\x04\x20\x00\x04\x01\x00\x00\x01\x01\x01", 14),
    ]


class SAPHDBInitializationReply(Packet):
    """SAP HANA SQL Command Network Protocol Initialization Reply packet

    This packet is used for the HANA SQL Command Network Protocol during initialization.
    """
    name = "SAP HANA SQL Command Network Protocol Initialization Reply"
    fields_desc = [
        LESignedByteField("product_major", 0),
        ShortField("product_minor", 0),
        LESignedByteField("protocol_major", 0),
        ShortField("protocol_minor", 0),
        ShortField("padding", 0),
    ]


class SAPHDBAuthenticationError(Exception):
    """SAP HDB Authentication exception"""


class SAPHDBAuthMethod(object):
    """SAP HDB Authentication Method

    This is the base class to define the authentication methods to use on
    a connection.
    """

    METHOD = None

    def __init__(self, username, pid=None, hostname=None):
        self.username = username
        self.pid = pid
        self.hostname = hostname

    @property
    def client_id(self):
        """Returns the Client Id to use when authenticating and connecting to the
        server."""
        pid = self.pid or "pysap"
        hostname = self.hostname or socket.gethostname()
        return "{}@{}".format(pid, hostname)

    def craft_authentication_request(self, value=None):
        """Craft the initial authentication request"""
        auth_fields = SAPHDBPartAuthentication(auth_fields=[SAPHDBPartAuthenticationField(value=self.username),
                                                            SAPHDBPartAuthenticationField(value=self.METHOD),
                                                            SAPHDBPartAuthenticationField(value=value)])
        auth_part = SAPHDBPart(partkind=33, argumentcount=1, buffer=auth_fields)
        auth_segm = SAPHDBSegment(messagetype=65, parts=[auth_part])
        return SAPHDB(segments=[auth_segm])

    def craft_authentication_response_part(self, value=None):
        auth_fields = SAPHDBPartAuthentication(auth_fields=[SAPHDBPartAuthenticationField(value=self.username),
                                                            SAPHDBPartAuthenticationField(value=self.METHOD),
                                                            SAPHDBPartAuthenticationField(value=value)])
        return SAPHDBPart(partkind=33, argumentcount=1, buffer=auth_fields)

    def authenticate(self, connection):
        """Method to authenticate the client connection.

        :param connection: connection to the server
        :type connection: :class:`SAPHDBConnection`

        :return: authentication part to use in Connect packet
        :rtype: SAPHDBPart

        :raise: SAPHDBAuthenticationError
        """
        raise NotImplemented("Authentication method not implemented")


class SAPHDBAuthScramMethod(SAPHDBAuthMethod):
    """SAP HDB Authentication using a SCRAM-based algorithm

    This base class is used to abstract the common implementation across different
    algorithms.
    """

    SCRAM_CLASS = None

    def __init__(self, username, password, pid=None, hostname=None):
        super(SAPHDBAuthScramMethod, self).__init__(username, pid=pid, hostname=hostname)
        self.password = password

    def obtain_client_proof(self, scram, client_key, auth_response_part):
        # Obtain the salt and the server key from the response
        method_parts = SAPHDBPartAuthentication(auth_response_part.auth_fields[1].value)
        salt = method_parts.auth_fields[0].value
        server_key = method_parts.auth_fields[1].value

        # Calculate the client proof from the password, salt and the server and client key
        # TODO: It might be good to see if this can be moved into a new Packet
        # TODO: We're only considering one server key
        client_proof = b"\x00\x01" + struct.pack('b', scram.CLIENT_PROOF_SIZE)
        client_proof += scram.scramble_salt(self.password, salt, server_key, client_key)

        return client_proof

    def authenticate(self, connection):
        """Perform the handshake using the scram method defined by the class"""

        scram = self.SCRAM_CLASS(default_backend())

        # Craft and send the authentication packet
        client_key = scram.get_client_key()
        auth_request = self.craft_authentication_request(client_key)
        auth_response = connection.sr(auth_request)
        auth_response_part = SAPHDBPartAuthentication(auth_response.segments[0].parts[0].buffer[0])

        # Check the method replied by the server
        if self.METHOD != auth_response_part.auth_fields[0].value:
            raise SAPHDBAuthenticationError("Authentication method not supported on server")

        # Craft authentication part and return it
        client_proof = self.obtain_client_proof(scram, client_key, auth_response_part)
        return self.craft_authentication_response_part(client_proof)


class SAPHDBAuthScramSHA256Method(SAPHDBAuthScramMethod):
    """SAP HDB Authentication using SCRAM-SHA256 algorithm.
    """
    METHOD = "SCRAMSHA256"
    SCRAM_CLASS = SCRAM_SHA256


class SAPHDBAuthScramPBKDF2SHA256Method(SAPHDBAuthScramMethod):
    """SAP HDB Authentication using SCRAM-PBKDF2-SHA256 algorithm.
    """
    METHOD = "SCRAMPBKDF2SHA256"
    SCRAM_CLASS = SCRAM_PBKDF2SHA256

    def obtain_client_proof(self, scram, client_key, auth_response_part):
        # Obtain the salt, the server key and the number of rounds from the response
        method_parts = SAPHDBPartAuthentication(auth_response_part.auth_fields[1].value)
        salt = method_parts.auth_fields[0].value
        server_key = method_parts.auth_fields[1].value
        rounds, = struct.unpack('>I', method_parts.auth_fields[2].value)

        # Calculate the client proof from the password, salt, rounds and the server and client key
        # TODO: It might be good to see if this can be moved into a new Packet
        # TODO: We're only considering one server key
        client_proof = b"\x00\x01" + struct.pack('b', scram.CLIENT_PROOF_SIZE)
        client_proof += scram.scramble_salt(self.password, salt, server_key, client_key, rounds)
        return client_proof


class SAPHDBAuthSessionCookieMethod(SAPHDBAuthMethod):
    """SAP HDB Authentication using a Session Cookie.
    """

    METHOD = "SessionCookie"

    def __init__(self, username, session_cookie, pid=None, hostname=None):
        super(SAPHDBAuthSessionCookieMethod, self).__init__(username, pid=pid, hostname=hostname)
        self.session_cookie = session_cookie

    def authenticate(self, connection):
        session_cookie = self.session_cookie + self.client_id
        auth_request = self.craft_authentication_request(session_cookie)

        auth_response = connection.sr(auth_request)
        auth_response_part = SAPHDBPartAuthentication(auth_response.segments[0].parts[0].buffer[0])

        # Check the method replied by the server
        if self.METHOD != auth_response_part.auth_fields[0].value:
            raise SAPHDBAuthenticationError("Authentication method not supported on server")

        # Craft authentication part and return it
        return self.craft_authentication_response_part()


class SAPHDBAuthJWTMethod(SAPHDBAuthMethod):
    """SAP HDB Authentication using JWT (JSON Web Token).
    """

    METHOD = "JWT"

    def __init__(self, username, jwt, pid=None, hostname=None):
        super(SAPHDBAuthJWTMethod, self).__init__(pid, hostname)
        self.username = username
        self.jwt = jwt

    def authenticate(self, connection):
        auth_request = self.craft_authentication_request(self.jwt)
        auth_request.show()

        auth_response = connection.sr(auth_request)
        auth_response_part = SAPHDBPartAuthentication(auth_response.segments[0].parts[0].buffer[0])

        # Check the method replied by the server
        if self.METHOD != auth_response_part.auth_fields[0].value:
            raise SAPHDBAuthenticationError("Authentication method not supported on server")

        # Craft authentication part and return it
        return self.craft_authentication_response_part()


class SAPHDBAuthSAMLMethod(SAPHDBAuthMethod):
    """SAP HDB Authentication using Security Assertion Markup Language (SAML) 2.0 Bearer Assertions.
    """

    METHOD = "SAML"

    def __init__(self, username, saml_assertion, pid=None, hostname=None):
        super(SAPHDBAuthSAMLMethod, self).__init__(pid, hostname)
        self.username = username
        self.saml_assertion = saml_assertion

    def authenticate(self, connection):
        auth_request = self.craft_authentication_request(self.saml_assertion)
        auth_request.show()

        auth_response = connection.sr(auth_request)
        auth_response_part = SAPHDBPartAuthentication(auth_response.segments[0].parts[0].buffer[0])

        # Check the method replied by the server
        if self.METHOD != auth_response_part.auth_fields[0].value:
            raise SAPHDBAuthenticationError("Authentication method not supported on server")

        # Craft authentication part and return it
        return self.craft_authentication_response_part()


saphdb_auth_methods = {
    "JWT": SAPHDBAuthJWTMethod,
    "SAML": SAPHDBAuthSAMLMethod,
    "SCRAMSHA256": SAPHDBAuthScramSHA256Method,
    "SCRAMPBKDF2SHA256": SAPHDBAuthScramPBKDF2SHA256Method,
    "SessionCookie": SAPHDBAuthSessionCookieMethod,
}
"""SAP HDB Authentication Methods Implemented"""


class SAPHDBConnectionError(Exception):
    """SAP HDB Connection exception
    """


class SAPHDBConnection(object):
    """SAP HDB Connection

    This class represents a basic client connection to a HANA server using
    the SQL Command Network Protocol.
    """

    def __init__(self, host, port, auth_method=None, route=None):
        """Creates the connection to the HANA server.

        :param host: remote host to connect to
        :type host: C{string}

        :param port: remote port to connect to
        :type port: ``int``

        :param auth_method: authentication method to use when connecting
        :type auth_method: :class:`SAPHDBAuthMethod`

        :param route: route to use for connecting through a SAP Router
        :type route: C{string}
        """
        self.host = host
        self.port = port
        self.auth_method = auth_method
        self.route = route
        self._stream_socket = None
        self.product_version = None
        self.protocol_version = None

    def connect(self):
        """Creates a :class:`SAPNIStreamSocket` connection to the host/port. If a route
        was specified, connect to the target HANA server through the SAP Router.
        """
        try:
            self._stream_socket = SAPRoutedStreamSocket.get_nisocket(self.host,
                                                                     self.port,
                                                                     self.route,
                                                                     base_cls=SAPHDB,
                                                                     talk_mode=1)
        except socket.error as e:
            raise SAPHDBConnectionError("Error connecting to the server (%s)" % e)

    def is_connected(self):
        return self._stream_socket is not None

    def send(self, message):
        if not self.is_connected():
            raise SAPHDBConnectionError("Socket not ready")
        self._stream_socket.send(message)

    def sr(self, message):
        if not self.is_connected():
            raise SAPHDBConnectionError("Socket not ready")
        self.send(message)
        return self.recv()

    def recv(self):
        if not self.is_connected():
            raise SAPHDBConnectionError("Socket not ready")
        # First we receive the header to obtain the variable length field
        header_raw = self._stream_socket.ins.recv(32)
        header = SAPHDB(header_raw)
        # Then get the payload
        payload = ""
        if header.varpartlength > 0:
            payload = self._stream_socket.ins.recv(header.varpartlength)
        # And finally construct the whole packet with header plus payload
        return SAPHDB(header_raw + payload)

    def initialize(self):
        """Initializes the connection with the server.
        """
        if not self.is_connected():
            raise SAPHDBConnectionError("Socket not ready")

        if self.product_version is not None and self.protocol_version is not None:
            return

        # Send initialization request packet
        init_request = SAPHDBInitializationRequest()
        self.send(init_request)

        # Receive initialization response packet
        init_reply = SAPHDBInitializationReply(self._stream_socket.recv(8))  # We use the raw socket recv here
        self.product_version = init_reply.product_major
        self.protocol_version = init_reply.protocol_major

    def authenticate(self):
        """Authenticates the connection against the server using the selected method.
        """
        if not self.is_connected():
            raise SAPHDBConnectionError("Socket not ready")

        # Perform the handshake and obtain the authentication part
        auth_part = self.auth_method.authenticate(self)

        # Craft the connect packet
        clientid_part = SAPHDBPart(partkind=35, buffer=self.auth_method.client_id)
        auth_segm = SAPHDBSegment(messagetype=66, parts=[auth_part, clientid_part])
        auth_request = SAPHDB(segments=[auth_segm])

        # Send connect packet
        auth_response = self.sr(auth_request)

        if auth_response.segments[0].segmentkind == 5:  # If is Error segment kind
            self.close_socket()
            raise SAPHDBAuthenticationError("Authentication failed")

        auth_response.show()

    def connect_authenticate(self):
        """Connects to the server, performs initialization and authenticates the client.
        """
        if not self.is_connected():
            self.connect()
        self.initialize()
        self.authenticate()

    def close(self):
        """Closes the connection with the server
        """
        if not self.is_connected():
            raise SAPHDBConnectionError("Connection already closed")

        try:
            disconnect_segm = SAPHDBSegment(messagetype=77)
            disconnect_request = SAPHDB(segments=[disconnect_segm])

            # Send disconnect packet and check the response
            disconnect_response = self.sr(disconnect_request)
            if disconnect_response.segments[0].segmentkind != 2 or \
               disconnect_response.segments[0].functioncode != 18:
                raise SAPHDBConnectionError("Connection incorrectly closed")

        except socket.error as e:
            raise SAPHDBConnectionError("Error closing the connection to the server (%s)" % e)

        finally:
            self.close_socket()

    def close_socket(self):
        """Closes the underlaying socket of the connection
        """
        self._stream_socket.close()
        self._stream_socket = None


class SAPHDBTLSConnection(SAPHDBConnection):
    """SAP HDB Connection using TLS

    This class wraps the connection socket with a TLS-enabled one for use as a secure channel.
    """

    def connect(self):
        # Create a plain socket first
        plain_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        plain_socket.settimeout(10)

        # TLS/SSL Context
        context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1  # optional
        context.verify_mode = ssl.CERT_NONE
        context.set_default_verify_paths()

        # Wrap the plain socket in a TLS/SSL one
        tls_socket = context.wrap_socket(plain_socket, server_hostname=self.host)
        tls_socket.connect((self.host, self.port))

        # Create the stream socket from the TLS/SSL one. From here treatment should be similar to a plain one.
        self._stream_socket = SSLStreamSocket(tls_socket, basecls=SAPHDB)


# Bind SAP NI with the HDB ports
bind_layers(TCP, SAPHDB, dport=30013)
bind_layers(TCP, SAPHDB, dport=30015)
