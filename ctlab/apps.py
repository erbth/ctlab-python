from ctlab import ctlab
import numpy as np
from matplotlib import pyplot
import time
import csv

class bipolar_transistor_characteristics:
    def __init__(self, adaio, dcg, resistor, max_base_current, ce_current_limit=100e-3):
        if not adaio or not dcg:
            raise ctlab.InvalidParameterException()

        self.adaio = adaio
        self.dcg = dcg
        self.resistor = resistor
        self.max_base_current = max_base_current
        self.max_base_voltage = np.amin([float(self.max_base_current) * resistor, 10.])
        self.ce_current_limit = ce_current_limit
        self.values = None

        self.reset_outputs()

        print("Base resistor has %s Ohm" % self.resistor)
        print("\nADA-IO is %s fw %s" % self.adaio.query_identity())
        print("DCG    is %s fw %s" % self.dcg.query_identity())
        print("\nMaximum base current: %s Ampére" % self.max_base_current)
        print("Derived maximum base voltage output: %s Volt" % self.max_base_voltage)
        print("\nThe C-E current limit is %s Ampére." % self.ce_current_limit)
        print("\nConnect one end of the base resistor to DA12-0 and the other to the base.")
        print("Connect AD16-0 to the base and the C-E way of the transistor to DCG.")

    def reset_outputs(self):
        self.dcg.display_power()
        self.adaio.display_da12(0)

        self.adaio.set_da12(0, 0)
        self.dcg.set_dca(0)

    def emergency_stop(self):
        print("Emergency stop engaged, trying to disable output ...")
        self.reset_outputs()
        print("Successfully disabled output.")

    def measure(self):
        try:
            self.dcg.set_dcv(2)
            self.dcg.set_dca(self.ce_current_limit)

        except Exception as e:
            self.emergency_stop()
            raise e

        # Initial assumed values
        ce_voltage = -100.
        ce_current = -100.
        be_voltage = -100.

        # List of tuples (B-E voltage, B-E current, C-E voltage, C-E current, C-E current limited)
        values = []

        for base_voltage in np.arange(-0.3, np.amin([self.max_base_voltage + 0.005, 10.]), 0.005):
            try:
                self.adaio.set_da12(0, base_voltage)
                base_voltage_read = self.adaio.query_da12(0)
            except Exception as e:
                self.emergency_stop()
                raise e

            if abs(base_voltage_read - base_voltage) > 1e-5:
                print('delta %s - %s = %s' % (base_voltage_read, base_voltage, base_voltage_read - base_voltage))
                self.emergency_stop()
                raise CommunicationErrorException()

            try:
                # Wait for values to settle
                while True:
                    ce_voltage_old = ce_voltage
                    ce_current_old = ce_current
                    be_voltage_old = be_voltage

                    ce_voltage = self.dcg.query_msv()
                    ce_current = self.dcg.query_msa()
                    be_voltage = self.adaio.query_ad16(0)

                    if abs(ce_voltage - ce_voltage_old) < 0.1 and abs(ce_current - ce_current_old) < 0.005:
                        break

                ce_limited = self.dcg.query_status()['iconst']

            except Exception as e:
                self.emergency_stop()
                raise e

            values.append((be_voltage, (base_voltage - be_voltage) / self.resistor, ce_voltage, ce_current, ce_limited))

        self.values = values

        self.reset_outputs()


    def print_values(self):
        if not self.values:
            raise NoDataException()

        for value in self.values:
            bev, bec, cev, cec, cel = value

            print("B-E voltage = %s, B-E current = %s, C-E voltage = %s, C-E current = %s, C-E current limited = %s" % (bev, bec, cev, cec, cel))

    def export_values_csv(self, name):
        if not self.values:
            raise NoDataException()

        if not name:
            raise ctlab.InvalidParameterException()

        with open(name, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(["B-E voltage", "B-E current", "C-E voltage", "C-E current", "C-E current limited"])

            for value in self.values:
                writer.writerow(value)

            csvfile.close()

    def plot_values(self):
        if not self.values:
            raise NoDataException()

        bevs = []
        becs = []
        cevs = []
        cecs = []
        cels = []
        hfes = []

        for value in self.values:
            bev, bec, cev, cec, cel = value

            # If cec is limited hfe does not make sense
            hfe = cec / bec if not cel else 0

            bevs.append(bev)
            becs.append(bec)
            cevs.append(cev)
            cecs.append(cec)
            hfes.append(hfe)

        pyplot.subplot(2,2,1)
        pyplot.plot(becs, cecs, 'bx')
        pyplot.gca().set_xlim(0,max(becs) * 1.05)
        pyplot.gca().set_ylim(0,max(cecs) * 1.05)
        pyplot.xlabel("B-E current in Ampére")
        pyplot.ylabel("C-E current in Ampére")
        pyplot.title("C-E current vs. B-E current")
        
        pyplot.subplot(2,2,2)
        pyplot.plot(cecs, hfes, 'bx')
        pyplot.gca().set_xlim(0,max(cecs) * 1.05)
        pyplot.gca().set_ylim(0,max(hfes) * 1.05)
        pyplot.xlabel('C-E current in Ampére')
        pyplot.ylabel('hfe')
        pyplot.title('hfe vs. C-E current')
        
        pyplot.subplot(2,2,3)
        pyplot.plot(becs, bevs, 'bx')
        pyplot.gca().set_xlim(0,max(becs) * 1.05)
        pyplot.gca().set_ylim(0,max(bevs) * 1.05)
        pyplot.xlabel('B-E current in Ampére')
        pyplot.ylabel('B-E voltage in Volt')
        pyplot.title('B-E Voltage vs. B-E current')
        
        pyplot.subplot(2,2,4)
        pyplot.plot(becs, cevs, 'bx')
        pyplot.gca().set_xlim(0,max(becs) * 1.05)
        pyplot.gca().set_ylim(0,max(cevs) * 1.05)
        pyplot.xlabel('B-E current in Ampére')
        pyplot.ylabel('C-E voltage in Volt')
        pyplot.title('C-E Voltage vs. B-E current (saturation voltage)')

        pyplot.show()

# ****************************** Exceptions ******************************
class CommunicationErrorException(Exception):
    def __init__(self):
        super().__init__("Error in communication")

# This exception is to be raised if no data is available because a complex
# measuring procedure has not taken place yet.
class NoDataException(Exception):
    def __init__(self):
        super().__init__("There is no data available yet.")
