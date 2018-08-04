import re
import socket
import fcntl, os, errno

DEFAULT_BUFFER_SIZE = 4096

class Connection(object):
    recv_matching_re = re.compile('#(\d+):(\d+)=(-?(\d|\.)+)( +\[?([^\r\n]*)\]?)?[\r\n]*')

    @staticmethod
    def form_ctlab_message(id, data):
        return ("%s:%s\r\n" % (id, data)).encode('ascii')

    def __init__(self, buffer_size=DEFAULT_BUFFER_SIZE):
        self.modules = {}
        self.buffer_size = buffer_size
        self.buffer = ''

    def add_module(self, module):
        self.modules[module.id] = module

    def connect(self):
        pass

    def send(self, id, data):
        print(self.form_ctlab_message(id, data).decode('ascii'))

    # This is exported to allow synchronous communication with lab modules.
    def receive(self):
        pass

    # Usually called from outside, i.e. an event loop
    def data_input(self, data):
        if isinstance(data, bytes):
            data = data.decode('ascii')

        res = re.match(self.recv_matching_re, data)

        if res:
            mid = int(res.group(1))
            chid = int(res.group(2))
            value = res.group(3)
            comment = res.group(6)

            if mid in self.modules:
                self.modules[mid].recv_subch(chid, value, comment)

    def close(self):
        pass

    def is_connected(self):
        return True

class TCPIP_Connection(Connection):
    def __init__(self, hostname, port, buffer_size=DEFAULT_BUFFER_SIZE, nonblocking=False):
        super().__init__(buffer_size)

        self.port = port
        self.specified_hostname = hostname
        self.socket = None
        self.nonblocking=nonblocking

    def connect(self):
        if not self.socket:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            try:
                self.socket.connect((socket.gethostbyname(self.specified_hostname), self.port))

                if self.nonblocking:
                    fcntl.fcntl(self.socket, fcntl.F_SETFL, os.O_NONBLOCK)
            except Exception as e:
                self.close()
                raise e

            except:
                self.close()
                raise Exception("No idea what's going on.")

    def send(self, id, data):
        if self.socket:
            self.socket.send(self.form_ctlab_message(id, data))
        else:
            raise NoConnectionException()

    # This is nonblocking if specified during object creation.
    def receive(self):
        try:
            self.buffer = self.buffer + self.socket.recv(self.buffer_size).decode('ascii')
        except socket.error as e:
            if e.errno in [errno.EAGAIN, errno.EWOULDBLOCK]:
                return
            else:
                raise e

        lines=self.buffer.splitlines(keepends=True)

        self.buffer = ''

        for line in lines:
            if re.match(r'.*\r.*', line):
                self.data_input(line)
            else:
                self.buffer = self.buffer + line

    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None

    def is_connected(self):
        return True if self.socket else False

class Module(object):
    def __init__(self, id, connection=None):
        self.id = id
        self.connection = connection

        self.updated = {}
        self.values = {}

        if connection:
            connection.add_module(self)

    def send(self, data):
        if self.connection:
            self.connection.send(self.id, data)
        else:
            raise NoConnectionException()

    def set_subch(self, chid, value):
        if isinstance(value, float):
            value = "{0:.10f}".format(value)

        self.send("%s=%s" % (chid, value))

    def req_subch(self, chid):
        self.send("%s?" % chid)

    # Common communication
    # Asynchronous query functions
    def req_identity(self):
        self.req_subch(254)

    # No get status function as this is module type specific
    def req_status(self):
        self.req_subch(255)

    def get_identity(self):
        if 'firmware' in self.values and 'name' in self.values:
            return (self.values['name'], self.values['firmware'])
        else:
            raise NoValueException()

    # Synchronous query functions
    def query_identity(self):
        self.req_identity()
        self.wait_updated(254)
        return self.get_identity()

    def recv_subch(self, chid, value, comment):
        if chid == 254:
            self.values['firmware'] = value
            self.values['name'] = comment
            self.updated[254] = True


    # For synchronous communication
    def wait_updated(self, chid):
        self.updated[chid] = False

        while not self.updated[chid]:
            self.connection.receive()


class DCG(Module):
    def __init__(self, id, connection=None):
        super().__init__(id, connection=connection)
        self.status = {
            'iconst' : False
        }


    # Value change functions
    def set_dcv(self, dcv):
        self.set_subch(0, dcv)

    def set_dca(self, dca):
        self.set_subch(1, dca)


    # Asynchronous query functions
    def req_dcv(self):
        self.req_subch(0)

    def req_dca(self):
        self.req_subch(1)

    def req_msv(self):
        self.req_subch(10)

    def req_msa(self):
        self.req_subch(11)

    def req_tmp(self):
        self.req_subch(233)


    def get_dcv(self):
        if 'dcv' in self.values:
            return self.values['dcv']
        else:
            raise NoValueException()

    def get_dca(self):
        if 'dca' in self.values:
            return self.values['dca']
        else:
            raise NoValueException()

    def get_msv(self):
        if 'msv' in self.values:
            return self.values['msv']
        else:
            raise NoValueException()

    def get_msa(self):
        if 'msa' in self.values:
            return self.values['msa']
        else:
            raise NoValueException()

    def get_tmp(self):
        if 'tmp' in self.values:
            return self.values['tmp']
        else:
            raise NoValueException()

    # Returns a copy of the status dict
    def get_status(self):
        return self.status.copy()


    # Synchronous query functions
    def query_dcv(self):
        self.req_dcv()
        self.wait_updated(0)
        return self.get_dcv()

    def query_dca(self):
        self.req_dca()
        self.wait_updated(1)
        return self.get_dca()

    def query_msv(self):
        self.req_msv()
        self.wait_updated(10)
        return self.get_msv()

    def query_msa(self):
        self.req_msa()
        self.wait_updated(11)
        return self.get_msa()

    def query_tmp(self):
        self.req_tmp()
        self.wait_updated(233)
        return self.get_tmp()

    def query_status(self):
        self.req_status()
        self.wait_updated(255)
        return self.get_status()


    # Change the menu shown on the lcd display
    def display_voltage(self):
        self.set_subch(80, 0)

    def display_current(self):
        self.set_subch(80, 1)

    def display_ripplePercent(self):
        self.set_subch(80, 2)

    def display_rippleTon(self):
        self.set_subch(80, 3)

    def display_rippleToff(self):
        self.set_subch(80, 4)

    def display_trackChannel(self):
        self.set_subch(80, 5)

    def display_energy(self):
        self.set_subch(80, 6)

    def display_power(self):
        self.set_subch(80, 7)

    # Usually called from the connection
    def recv_subch(self, chid, value, comment):
        super().recv_subch(chid, value, comment)

        if chid == 0:
            self.values['dcv'] = float(value)
            self.updated[0] = True
        elif chid == 1:
            self.values['dca'] = float(value)
            self.updated[1] = True
        elif chid == 10:
            self.values['msv'] = float(value)
            self.updated[10] = True
        elif chid == 11:
            self.values['msa'] = float(value)
            self.updated[11] = True
        elif chid == 233:
            self.values['tmp'] = float(value)
            self.updated[233] = True
        elif chid == 255:
            self.status['iconst'] = True if re.match(r'.*ICONST.*', comment) else False
            self.updated[255] = True

class ADA_IO(Module):
    def __init__(self, id, connection=None):
        super().__init__(id, connection=connection)
        self.status = {
        }


    # Value change functions
    def set_da12(self, channel, voltage):
        if voltage < -10. or voltage > 10. or channel < 0 or channel > 7:
            raise InvalidParameterException()

        self.set_subch(channel + 20, voltage)


    # Asynchronous query functions
    def req_da12(self, channel):
        if channel < 0 or channel > 7:
            raise InvalidParameterException()

        self.req_subch(channel + 20)
      
    def req_ad16(self, channel):
        if channel < 0 or channel > 7:
            raise InvalidParameterException()

        self.req_subch(channel + 10)
      
    def req_ad10(self, channel):
        if channel < 0 or channel > 7:
            raise InvalidParameterException()

        self.req_subch(channel)
      

    def get_da12(self, channel):
        if channel < 0 or channel > 7:
            raise InvalidParameterException()

        channel = channel + 20

        if channel in self.values:
            return self.values[channel]
        else:
            raise NoValueException()

    def get_ad16(self, channel):
        if channel < 0 or channel > 7:
            raise InvalidParameterException()

        channel = channel + 10

        if channel in self.values:
            return self.values[channel]
        else:
            raise NoValueException()

    def get_ad10(self, channel):
        if channel < 0 or channel > 7:
            raise InvalidParameterException()

        if channel in self.values:
            return self.values[channel]
        else:
            raise NoValueException()


    # Synchronous query functions
    def query_da12(self, channel):
        if channel < 0 or channel > 7:
            raise InvalidParameterException()

        self.req_da12(channel)
        self.wait_updated(channel + 20)
        return self.get_da12(channel)

    def query_ad16(self, channel):
        if channel < 0 or channel > 7:
            raise InvalidParameterException()

        self.req_ad16(channel)
        self.wait_updated(channel + 10)
        return self.get_ad16(channel)

    def query_ad10(self, channel):
        if channel < 0 or channel > 7:
            raise InvalidParameterException()

        self.req_ad10(channel)
        self.wait_updated(channel)
        return self.get_ad10(channel)


    # Change the menu shown on the lcd display
    def display_ad10(self, channel):
        if channel < 0 or channel > 7:
            raise InvalidParameterException()

        self.set_subch(80, channel)

    def display_ad16(self, channel):
        if channel < 0 or channel > 7:
            raise InvalidParameterException()

        self.set_subch(80, channel + 10)

    def display_da12(self, channel):
        if channel < 0 or channel > 7:
            raise InvalidParameterException()

        self.set_subch(80, channel + 20)


    # Usually called from the connection
    def recv_subch(self, chid, value, comment):
        super().recv_subch(chid, value, comment)

        if chid >= 0 and chid <= 7 or chid >= 10 and chid <= 17 or chid >= 20 and chid <= 27:
            self.values[chid] = float(value)
            self.updated[chid] = True
        

# ****************************** Exceptions ******************************
class NoConnectionException(Exception):
    def __init__(self):
        super().__init__("No connection associated with this module")

# There is a connection but it's not connected to the lab.
class NotConnectedException(Exception):
    def __init__(self):
        super().__init__("The connections is not connected.")


# To be thrown if that value is not available (yet).
class NoValueException(Exception):
    def __init__(self):
        super().__init__("This value is not available (yet).")

# To be thrown if the user specified an invalid parameter value
class InvalidParameterException(Exception):
    def __init__(self):
        super().__init__("Invalid parameter")
