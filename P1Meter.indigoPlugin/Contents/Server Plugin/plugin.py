# !/usr/bin/env python
# -*- coding: utf-8 -*-
##########################################################################################
#
#   An Indigo plugin for reporting values from Dutch Smart Meters (P1 meters)
#   into an Indigo device
#
#   Copyright (C) 2020, Rudi Zengers, Netherlands
#
#   Permission is hereby granted, free of charge, to any person obtaining a copy
#   of this software and associated documentation files (the "Software"), to deal
#   in the Software without restriction, including without limitation the rights
#   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#   copies of the Software, and to permit persons to whom the Software is
#   furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in all
#   copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#   SOFTWARE.
#
#   More info on this Indigo plugin can be found on my website at
#   https://www.zengers.net/indigo/p1-meter-plugin/. 
# 
#   I am not a professional developer and I created this plugin for my own needs. 
#   This software might even have bugs. No, it _will_ have bugs and imperfections.
#   However if this plugin fits your needs and you want to help me improving I am 
#   happy to hear your positive feedback and learn from it. 
#
#   Version History 
#   ---------------
#    0.1.0   Mar 20, 2020   First developerversion
#    0.2.0   Apr 11, 2020   Switched engine class, see below now using github.com/nrocco/smeterd
#    1.0.0   Apr 23, 2020   Bumped version number to have first public Github version out
#
##########################################################################################

import sys
import serial
from serial.serialutil import SerialException
import re
import locale
from time import mktime
from datetime import datetime




class Plugin(indigo.PluginBase):
   ##########################################################################################
   #
   #   Our Plugin Class definition
   #
   ##########################################################################################

   #  Global variables
   logLevel            = "Normal"        # Default no debug logging
   usbDevice           = "None"          # On which USB port do we find the P1 neter
   dsmrversion         = "0"             # Not defined yet
   sleeptime           = 60              # Pause between reading telegrarms
   show_raw            = 0               # Show all raw telegrams
   max_telegram_length = 40              # Prevent looping over garbish

   def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
      ##########################################################################################
      #
      #   Initalization of the indigo base plugin and on top of it our plugin
      #
      ##########################################################################################
      indigo.PluginBase.__init__(self,pluginId,pluginDisplayName,pluginVersion,pluginPrefs)



   def __del__(self):
      ##########################################################################################
      #
      #   Delete of our plugin from memory
      #
      ##########################################################################################
      return



   def verbose(self, logtext):
      #########################################################################################
      #
      #   My own logger
      #
      ##########################################################################################
      if self.logLevel == "Verbose":
         self.logger.info(logtext)
      return



   def GetMasterDevList(self):
      ##########################################################################################
      #
      #   Get List of Master Devices
      #
      ##########################################################################################
      MasterDevList = indigo.devices.keys(filter="self.p1meter")
      if len(MasterDevList) == 0:
         # No Device yet so let's create it
         DevCreated = indigo.device.create(indigo.kProtocol.Plugin, name="P1 Master",
             description="Energy Management", deviceTypeId="p1meter")
         MasterDevList.append(DevCreated)
      return MasterDevList



   def SetMasterState(self,tekst):
      ##########################################################################################
      #
      #   Get List of Master Devices
      #
      ##########################################################################################
      MasterDevList = indigo.devices.keys(filter="self.p1meter")
      if len(MasterDevList) > 0:
         P1Dev = indigo.devices[MasterDevList[0]]
         P1Dev.updateStateOnServer("masterState",tekst)
      return



   def startup(self):
      ##########################################################################################
      #
      #   After the init we can start our plugin. Define actions here
      #
      ##########################################################################################
      self.verbose("Starting {} Plugin; version {}".format(self.pluginDisplayName,self.pluginVersion))
      self.verbose("For detailled logging, set level to Verbose in Plugin Config")

      #Check if config is complete by setting to default if no value is available
      self.logLevel           = self.pluginPrefs.get("logLevel","Normal")
      self.usbDevice          = self.pluginPrefs.get("usbDevice","None")
      self.dsmrversion        = self.pluginPrefs.get("dsmrversion","4")
      self.sleeptime          = int(self.pluginPrefs.get("sleeptime",120))
      self.show_raw           = int(self.pluginPrefs.get("show_raw",0))

      self.SetMasterState("Started")
      return



   def shutdown(self):
      ##########################################################################################
      #
      #   Plugin is requested to shutdown
      #
      ##########################################################################################
      self.verbose("....in shutdown sequence")
      self.SetMasterState("Stopped")
      return



   def validatePrefsConfigUi(self, valuesDict):
      ##########################################################################################
      #
      #   Validation of configuration input given. Is it within rainExpected values?
      #
      ##########################################################################################
      self.verbose("Starting validatePrefsConfig")
      errorDict = indigo.Dict()

      # Get usb device
      self.usbDevice = str(valuesDict["usbDevice"])
      self.verbose("USB device received %s" % self.usbDevice)

      # DSMR Version
      self.dsmrversion = str(valuesDict["dsmrversion"])
      self.verbose("DSMR version %s" % self.dsmrversion)

      # Log Level
      self.logLevel  = str(valuesDict["logLevel"])
      self.show_raw  = int(valuesDict["show_raw"])

      # time between measurements
      self.sleeptime = int(valuesDict["sleeptime"])

      # If we arrive here, all values are ok. Update Server on this
      self.logger.info("Plugin Config Updated succesfull")

      return (True,valuesDict)



   def store_indigo(self,P1Dev, keys):
      ##########################################################################################
      #
      #   Store the received packet in Indigo
      #
      ##########################################################################################

      sumup = int(1000 * (float(keys['kwh']['current_produced']) - float(keys['kwh']['current_consumed'])))
      if sumup > 0:
         mstate = "Producing {} W".format(sumup)
      else:
         mstate = "Consuming {} W".format(0-sumup)

      P1Dev.updateStatesOnServer([

            {'key':'meterType',                  'value':keys['header']['meterType']},
            {'key':'netManager',                 'value':keys['header']['netManager']},
            {'key':'textMessage',                'value':keys['msg']['text']},
            {'key':'meterID',                    'value':keys['kwh']['eid'].decode("hex")},
            {'key':'checkSum',                   'value':""},
            {'key':'dsmrVersion',                'value':keys['header']['dsmrVersion']},
            {'key':'timestamp',                  'value':keys['header']['measured_at']},
            {'key':'masterState',                'value':mstate},

            {'key':'currentTariff',              'value':keys['kwh']['tariff']},
            {'key':'currentNowPhase1',           'value':keys['kwh']['phase1']['amps']},
            {'key':'currentNowPhase2',           'value':keys['kwh']['phase2']['amps']},
            {'key':'currentNowPhase3',           'value':keys['kwh']['phase3']['amps']},
            {'key':'usedNowPhase1',              'value':float(keys['kwh']['phase1']['usedNow'])*1000},
            {'key':'usedNowPhase2',              'value':float(keys['kwh']['phase2']['usedNow'])*1000},
            {'key':'usedNowPhase3',              'value':float(keys['kwh']['phase3']['usedNow'])*1000},
            {'key':'generatedNowPhase1',         'value':float(keys['kwh']['phase1']['producedNow'])*1000},
            {'key':'generatedNowPhase2',         'value':float(keys['kwh']['phase2']['producedNow'])*1000},
            {'key':'generatedNowPhase3',         'value':float(keys['kwh']['phase3']['producedNow'])*1000},

            {'key':'outagesLongCount',           'value':keys['kwh']['outages']['longcount']},
            {'key':'outagesLongRecentDuration',  'value':keys['kwh']['outages']['duration']},
            {'key':'outagesLongRecentTimestamp', 'value':keys['kwh']['outages']['timestamp']},
            {'key':'outagesShortCount',          'value':keys['kwh']['outages']['shortcount']},

            {'key':'voltageNowPhase1',           'value':keys['kwh']['phase1']['volt']},
            {'key':'voltageNowPhase2',           'value':keys['kwh']['phase2']['volt']},
            {'key':'voltageNowPhase3',           'value':keys['kwh']['phase3']['volt']},
            {'key':'voltageToHighCountPhase1',   'value':keys['kwh']['phase1']['swells']},
            {'key':'voltageToHighCountPhase2',   'value':keys['kwh']['phase2']['swells']},
            {'key':'voltageToHighCountPhase3',   'value':keys['kwh']['phase3']['swells']},
            {'key':'voltageToLowCountPhase1',    'value':keys['kwh']['phase1']['saggs']},
            {'key':'voltageToLowCountPhase2',    'value':keys['kwh']['phase2']['saggs']},
            {'key':'voltageToLowCountPhase3',    'value':keys['kwh']['phase3']['saggs']},
 
            {'key':'usedT1',                     'value':keys['kwh']['low']['consumed']},
            {'key':'usedT2',                     'value':keys['kwh']['high']['consumed']},
            {'key':'generatedT1',                'value':keys['kwh']['low']['produced']},
            {'key':'generatedT2',                'value':keys['kwh']['high']['produced']},

            {'key':'nowGenerated',               'value':float(keys['kwh']['current_produced'])*1000},
            {'key':'nowUnit',                    'value':"W"},
            {'key':'nowUsage',                   'value':float(keys['kwh']['current_consumed'])*1000},
            {'key':'nowSum',                     'value':sumup},
            {'key':'tariffUnit',                 'value':"kWh"},

            {'key':'gastimestamp',               'value':keys['gas']['measured_at']},
            {'key':'gasused',                    'value':float(keys['gas']['total'])},
            {'key':'gastariffUnit',              'value':keys['gas']['unit']},
            {'key':'gasMeterID',                 'value':keys['gas']['eid'].decode("hex")},
            {'key':'gasMeterType',               'value':keys['gas']['device_type']},
            {'key':'gasValve',                   'value':keys['gas']['valve']}
      ])
      return



   def readtelegram(self,P1Dev):
      ##########################################################################################
      #
      #   Read a complete telegram from meter
      #
      ##########################################################################################
      
      if self.usbDevice == "None":
         self.logger.info(u"Configuration not yet complete; Please specify which device to use")
         return

      if self.dsmrversion == "2":
         # DSMR 2.2 > 9600 7E1:
         meter = SmartMeter(self, 
                    self.usbDevice,
                    baudrate=9600,
                    bytesize=7,
                    parity="E",
                    stopbits=1,
                    xonxoff=0,
                    timeout=10,
         )

      if self.dsmrversion == "4":
         # DSMR 4.0/4.2 > 115200 8N1:
         meter = SmartMeter(self,
                    self.usbDevice,
                    baudrate=115200,
                    bytesize=8,
                    parity="N",
                    stopbits=1,
                    xonxoff=0,
                    timeout=10,
         )

      try:
        packet = meter.read_one_packet()
      except SerialException as e:
        parser.error(e)
      finally:
        meter.disconnect()

      if self.show_raw == 1:
         print(str(packet))
         
      self.store_indigo(P1Dev,packet)
      return



   def runConcurrentThread(self):
      ##########################################################################################
      #
      # This function will loop forever and only return after self.stopThread becomes True
      #
      ##########################################################################################

      self.verbose("Plugin running state")
      try:
         #  Until we are requested to stop
         while True:
            # Act for all defined Master Devices
            MasterDevList = self.GetMasterDevList()
            if len(MasterDevList) > 1:
               self.verbose("Expecting exactly 1 P1 Device but found {}. Correct please".format(len(MasterDevList)))
            else:
                P1Dev = indigo.devices[MasterDevList[0]] 
                self.readtelegram(P1Dev)

            self.sleep(self.sleeptime) # Ready for now. Sleep again till next minute

      except self.StopThread:
         pass
      self.verbose("Plugin will stop") # We will only arrive here after a plugin stop command



##########################################################################################
#
#   SmartMeter class https://github.com/nrocco/smeterd/blob/master/smeterd/meter.py
#
# Copyright (c) 2013, Nico Di Rocco.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
##########################################################################################

class SmartMeter(object):
   serial_defaults = {
       'baudrate': 9600,
       'bytesize': serial.SEVENBITS,
       'parity': serial.PARITY_EVEN,
       'stopbits': serial.STOPBITS_ONE,
       'xonxoff': False,
       'timeout': 10,
   }



   def __init__(self, Plugin, port, **kwargs):
      ##########################################################################################
      #
      #   Initalization of the indigo base plugin and on top of it our plugin
      #
      ##########################################################################################
      config = {}
      config.update(self.serial_defaults)
      config.update(kwargs)
      self.Plugin = Plugin
      Plugin.verbose("Open serial connect to {} with: {}".format(port, ", ".join("{}={}".format(key, value) for key, value in config.items())))

      try:
         self.serial = serial.Serial(port, **config)
      except (serial.SerialException,OSError) as e:
         raise SmartMeterError(e)
      else:
         self.serial.setRTS(False)
         self.port = self.serial.name

      Plugin.verbose("New serial connection opened to {}".format(self.serial.name))



   def connect(self):
      if not self.serial.isOpen():
         Plugin.verbose("Opening connection to '{}'".format(self.serial.name))
         self.serial.open()
         self.serial.setRTS(False)
      else:
         self.Plugin.verbose("'{}' was already open".format(self.serial.name))



   def disconnect(self):
      if self.serial.isOpen():
         self.Plugin.verbose("Closing connection to '{}'".format(self.serial.name))
         self.serial.close()
      else:
         self.Plugin.verbose("'{}' was already closed".format(self.serial.name))



   def connected(self):
      return self.serial.isOpen()



   def read_one_packet(self):
      datagram = b''
      lines_read = 0
      startFound = False
      endFound = False

      self.Plugin.verbose("Start reading lines")

      while not startFound or not endFound or lines_read < Plugin.max_telegram_length:
         try:
            line = self.serial.readline()
            #self.Plugin.verbose("{}".format(line.decode('ascii').rstrip()))
         except Exception as e:
            self.Plugin.verbose(e)
            self.Plugin.verbose("Read a total of {} lines".format(lines_read))
            raise SmartMeterError(e)

         lines_read += 1

         if re.match(b'.*(?=/)', line):
            startFound = True
            endFound = False
            datagram = line.lstrip()
         elif re.match(b'(?=!)', line):
            endFound = True
            datagram = datagram + line
         else:
            datagram = datagram + line

      self.Plugin.verbose("Done reading one packet (containing {} lines)".format(len(datagram.splitlines())))
      self.Plugin.verbose("Total lines read from serial port: {}".format(lines_read))
      self.Plugin.verbose("Constructing P1Packet from raw data")

      return P1Packet(datagram)

   def __enter__(self):
      return self

   def __exit__(self, type, value, traceback):
      self.disconnect()



class SmartMeterError(Exception):
   pass



class P1PacketError(Exception):
   pass



class P1Packet(object):
   _datagram = ''

   def ts(self,v):
      return  "20{}-{}-{}T{}:{}:{}".format(v[0:2],v[2:4],v[4:6],v[6:8],v[8:10],v[10:12])

   def __init__(self, datagram):
      self._datagram = datagram

      #self.validate()

      keys = {}
      keys['header'] = {}
      keys['msg'] = {}
      keys['kwh'] = {}
      keys['kwh']['low'] = {}
      keys['kwh']['high'] = {}
      keys['kwh']['outages'] = {}
      keys['kwh']['phase1'] = {}
      keys['kwh']['phase2'] = {}
      keys['kwh']['phase3'] = {}
      
      # /Ene5\T210-D ESMR5.0
      #  ^^^
      keys['header']['netManager'] = self.get(b'^/s*(.{3})')

      # /Ene5\T210-D ESMR5.0
      #       ^^^^^^
      keys['header']['meterType'] = self.get(b'^(?:/s*.{3}.{2})(\S*)(?:.*)')

      # 1-3:0.2.8(50)
      #           ^^
      keys['header']['dsmrVersion'] = self.get(b'^(?:1\-3\:0\.2\.8\()(.*)(?:\))')
      # 0-0:1.0.0(200411171526S)
      #           ^^^^^^^^^^^^
      keys['header']['measured_at'] = self.ts(self.get(b'^(?:0-0:1\.0\.0\()(\d*)'))

      # 0-0:96.1.1(4530303438303030303235313238343138)
      #            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      keys['kwh']['eid'] = self.get(b'^0-0:96\.1\.1\(([^)]+)\)')

      # 0-0:96.14.0(0001)
      #             ^^^^
      keys['kwh']['tariff'] = self.get_int(b'^0-0:96\.14\.0\(([0-9]+)\)')

      # 0-0:96.3.10(?)
      #             ^
      keys['kwh']['switch'] = self.get_int(b'^0-0:96\.3\.10\((\d)\)')

      # 0-0:17.0.0(????.??*kW)
      #            ^^^^^^^
      keys['kwh']['treshold'] = self.get_float(b'^0-0:17\.0\.0\(([0-9]{4}\.[0-9]{2})\*kW\)')

      # 1-0:1.8.1(004486.031*kWh)
      #           ^^^^^^^^^^
      keys['kwh']['low']['consumed'] = self.get(b'^1-0:1\.8\.1\(([0-9]+\.[0-9]+)\*kWh\)')
      
      # 1-0:2.8.1(000732.442*kWh)
      #           ^^^^^^^^^^
      keys['kwh']['low']['produced'] = self.get(b'^1-0:2\.8\.1\(([0-9]+\.[0-9]+)\*kWh\)')

       # 1-0:1.8.2(002272.913*kWh)
      #           ^^^^^^^^^^
      keys['kwh']['high']['consumed'] = self.get(b'^1-0:1\.8\.2\(([0-9]+\.[0-9]+)\*kWh\)')
      
      # 1-0:2.8.2(001838.277*kWh)
      #           ^^^^^^^^^^
      keys['kwh']['high']['produced'] = self.get(b'^1-0:2\.8\.2\(([0-9]+\.[0-9]+)\*kWh\)')

      # 1-0:1.7.0(00.000*kW)
      #           ^^^^^^^^^^
      keys['kwh']['current_consumed'] = self.get(b'^1-0:1\.7\.0\(([0-9]+\.[0-9]+)\*kW\)')

      # 1-0:2.7.0(02.403*kW)
      #           ^^^^^^^^^^
      keys['kwh']['current_produced'] = self.get(b'^1-0:2\.7\.0\(([0-9]+\.[0-9]+)\*kW\)')

      # 0-0:96.7.21(00673)
      #             ^^^^^
      keys['kwh']['outages']['shortcount'] = int(self.get(b'^0-0:96\.7\.21\((\d*)'))

      # 0-0:96.7.9(00006)
      #             ^^^^^
      keys['kwh']['outages']['longcount'] = int(self.get(b'^0-0:96\.7\.9\((\d*)'))

      # 1-0:99.97.0(1)(0-0:96.7.19)(180806173744S)(0000000737*s)
      #                             ^^^^^^^^^^^^^
      keys['kwh']['outages']['timestamp'] = self.ts(self.get(b'^(?:1-0:99\.97\.0\([0-9*]\)\(0-0\:96\.7\.19\)\()(\d*)'))

     # 1-0:99.97.0(1)(0-0:96.7.19)(180806173744S)(0000000737*s)
      #                                           ^^^^^^^^^^
      keys['kwh']['outages']['duration'] = int(self.get(b'^(?:1-0:99\.97\.0\([0-9*]\)\(0-0\:96\.7\.19\)\()\d*[SW]\)\((\d*)'))

      # 1-0:32.32.0(00002)
      #             ^^^^^
      keys['kwh']['phase1']['saggs'] = int(self.get(b'^(?:1-0:32\.32\.0\()(\d*)'))

      # 1-0:52.32.0(00002)
      #             ^^^^^
      keys['kwh']['phase2']['saggs'] = int(self.get(b'^(?:1-0:52\.32\.0\()(\d*)'))

      # 1-0:72.32.0(00002)
      #             ^^^^^
      keys['kwh']['phase3']['saggs'] = int(self.get(b'^(?:1-0:72\.32\.0\()(\d*)'))

      # 1-0:32.36.0(00000)
      #             ^^^^^
      keys['kwh']['phase1']['swells'] = int(self.get(b'^(?:1-0:32\.36\.0\()(\d*)'))

      # 1-0:52.36.0(00000)
      #             ^^^^^
      keys['kwh']['phase2']['swells'] = int(self.get(b'^(?:1-0:52\.36\.0\()(\d*)'))

      # 1-0:72.36.0(00000)
      #             ^^^^^
      keys['kwh']['phase3']['swells'] = int(self.get(b'^(?:1-0:72\.36\.0\()(\d*)'))

      # 1-0:32.7.0(235.0*V)
      #            ^^^^^
      keys['kwh']['phase1']['volt'] = int(self.get(b'^(?:1-0:32\.7\.0\()(\d*)'))

      # 1-0:52.7.0(233.0*V)
      #            ^^^^^
      keys['kwh']['phase2']['volt'] = int(self.get(b'^(?:1-0:52\.7\.0\()(\d*)'))

      # 1-0:72.7.0(238.0*V)
      #            ^^^^^
      keys['kwh']['phase3']['volt'] = int(self.get(b'^(?:1-0:72\.7\.0\()(\d*)'))

      # 1-0:31.7.0(003*A)
      #            ^^^
      keys['kwh']['phase1']['amps'] = int(self.get(b'^(?:1-0:31\.7\.0\()(\d*)'))

      # 1-0:51.7.0(003*A)
      #            ^^^
      keys['kwh']['phase2']['amps'] = int(self.get(b'^(?:1-0:51\.7\.0\()(\d*)'))

      # 1-0:71.7.0(004*A)
      #            ^^^
      keys['kwh']['phase3']['amps'] = int(self.get(b'^(?:1-0:71\.7\.0\()(\d*)'))

      # 1-0:21.7.0(00.000*kW)
      #            ^^^^^^
      keys['kwh']['phase1']['usedNow'] = self.get(b'^(?:1-0:21\.7\.0\()(\d*\.\d*)')

      # 1-0:41.7.0(00.000*kW)
      #            ^^^^^^
      keys['kwh']['phase2']['usedNow'] = self.get(b'^(?:1-0:41\.7\.0\()(\d*\.\d*)')

      # 1-0:61.7.0(00.000*kW)
      #            ^^^^^^
      keys['kwh']['phase3']['usedNow'] = self.get(b'^(?:1-0:61\.7\.0\()(\d*\.\d*)')

      # 1-0:22.7.0(00.768*kW)
      #            ^^^^^^
      keys['kwh']['phase1']['producedNow'] = self.get(b'^(?:1-0:22\.7\.0\()(\d*\.\d*)')

      # 1-0:42.7.0(00.699*kW)
      #            ^^^^^^
      keys['kwh']['phase2']['producedNow'] = self.get(b'^(?:1-0:42\.7\.0\()(\d*\.\d*)')

      # 1-0:62.7.0(00.935*kW)
      #            ^^^^^^
      keys['kwh']['phase3']['producedNow'] = self.get(b'^(?:1-0:62\.7\.0\()(\d*\.\d*)')

      keys['gas'] = {}
      # 0-1:24.2.1(200411171500S)(00889.906*m3)
      #                                     ^^
      keys['gas']['unit'] = self.get(b'^(?:0-1:24\.2\.1(?:\(\d+[SW]\))?)?\([0-9]{5}\.[0-9]{3}(?:\*(\S*))\)', 0)

      # 0-1:96.1.0(4730303538353330303337363337333139)
      #            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      keys['gas']['eid'] = self.get(b'^0-1:96\.1\.0\(([^)]+)\)')

      # 0-1:24.1.0(003)
      #            ^^^
      keys['gas']['device_type'] = self.get_int(b'^0-1:24\.1\.0\((\d)+\)')
      
      # 0-1:24.2.1(200411171500S)(00889.906*m3)
      #            ^^^^^^^^^^^^^
      measured_at = self.get(b'^(?:0-1:24\.[23]\.[01](?:\((\d+)[SW]?\))?)')
      if measured_at:
         keys['gas']['measured_at'] = self.ts(measured_at)
      else:
         keys['gas']['measured_at'] = None

      # 0-1:24.2.1(200411171500S)(00889.906*m3)
      #                           ^^^^^^^^^
      keys['gas']['total'] = self.get(b'^(?:0-1:24\.2\.1(?:\(\d+[SW]\))?)?\(([0-9]{5}\.[0-9]{3})(?:\*m3)\)', 0)

      # 0-1:24.4.0(????)
      #            ^^^^
      keys['gas']['valve'] = self.get_int(b'^0-1:24\.4\.0\((\d)\)')

      # 0-0:96.13.1( )
      #             ^
      keys['msg']['code'] = self.get(b'^0-0:96\.13\.1\((\d+)\)')

      # 0-0:96.13.0( )
      #             ^
      keys['msg']['text'] = self.get(b'^0-0:96\.13\.0\((.+)\)')

      self._keys = keys



   def __getitem__(self, key):
      return self._keys[key]



   def get_float(self, regex, default=None):
      result = self.get(regex, None)
      if not result:
         return default
         return float(result)



   def get_int(self, regex, default=None):
      result = self.get(regex, None)
      if not result:
         return default
      return int(result)



   def get(self, regex, default=None):
      results = re.search(regex, self._datagram, re.MULTILINE)
      if not results:
         return default
      return results.group(1).decode('ascii')



   def validate(self):
      pattern = re.compile(b'\r\n(?=!)')
      for match in pattern.finditer(self._datagram):
         packet = self._datagram[:match.end() + 1]
         checksum = self._datagram[match.end() + 1:]

      if checksum.strip():
         given_checksum = int('0x' + checksum.decode('ascii').strip(), 16)
         #calculated_checksum = crc16(packet)

         #if given_checksum != calculated_checksum:
            #Plugin.verbose("Checksum mismatch: given={}, calculated={}".format(given_checksum, calculated_checksum))
            #raise P1PacketError("P1Packet with invalid checksum found")



   def __str__(self):
       return self._datagram.decode('ascii')
