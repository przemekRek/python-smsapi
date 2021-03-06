#! /usr/bin/env python
    #
    # python-smsapi - Python bindings for the smsapi.pl SOAP API
    #
    # Copyright (c) 2010, Grzegorz Bialy, ELCODO.pl
    # All rights reserved.
    #
    # Redistribution and use in source and binary forms, with or without
    # modification, are permitted provided that the following conditions are met:
    #     * Redistributions of source code must retain the above copyright
    #       notice, this list of conditions and the following disclaimer.
    #     * Redistributions in binary form must reproduce the above copyright
    #       notice, this list of conditions and the following disclaimer in the
    #       documentation and/or other materials provided with the distribution.
    #     * Neither the name of the author nor the names of its contributors may
    #       be used to endorse or promote products derived from this software
    #       without specific prior written permission.
    #
    # THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS``AS IS'' AND ANY
    # EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
    # WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
    # DISCLAIMED. IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE FOR ANY
    # DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
    # (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
    # LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
    # ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
    # (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
    # SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from suds.client import Client
from suds import WebFault
import hashlib
import time


__all__ = ['SmsApi']

VERSION = '0.1'

WSDL_URL = "https://ssl.smsapi.pl/api/soap/v2/webservices?WSDL"


class SmsApiException(Exception):

    def __init__(self, msg, args=[]):
        self.msg = msg
        self.args = args

    def __unicode__(self):
        return 'SmsApi Exception: %s' % self.msg


class SmsApiBaseObject(object):

    def __init__(self, username, password):
        """Set username and password"""
        self.username = username
        self.password = hashlib.md5(password).hexdigest()
        self.client = Client(WSDL_URL)
        self.user = self._prepare_user()

    def _prepare_user(self):
        """Prepare User object for authentication"""
        user = self.client.factory.create('Client')
        user.username = self.username
        user.password = self.password
        return user

    def _executeSMSApi(self, smsApiMethod, params):
        """Execute smsApi soup request
        
        in case of webfault exception there will be key 'error_webfault' 
        present within result dictionary

        """  

        result = {}
        try:
            result.update(smsApiMethod(**params))
        except WebFault, e:
            result['error_webfault'] = unicode(e.fault['faultstring'])
        finally:
            return self._flatenResult(result)

    def _flatenResult(self, result):
        for key, value in result.items():
            if isinstance(value, list):
                result[key] = value[0]

        return result


class SmsApiAddressBook(SmsApiBaseObject):
    """Address Book contains numbers and groups of numbers"""

    def get_groups(self):
        """Return list of groups"""
        response = self.client.service.get_groups(
            self.username,
            self.password,
        )
        if not "groups" in response:
            return None
        retlist = []
        for g in response['groups']:
            retlist.append({
                'id': int(g['id']),
                'name': unicode(g['name']),
                'description': unicode(g['info']),
                'number_count': int(g['num_count']),
            })
        return retlist

    def add_group(self, name, description=u""):
        """Add group. Return ID (int) if added, Exception otherwise"""
        response = self.client.service.add_group(self.user, name, description)
        try:
            return response['group_id']
        except KeyError:
            pass
        raise SmsApiException("Couldn't add group")

    def delete_group(self, id):
        """Delete group by given id. Returns True if deleted or error dict"""
        response = self.client.service.delete_group(self.user, int(id))
        if "result" in response and response["result"] == 0:
            return True
        return {
            'code': response['result'],
            'description': response['description'],
        }

    def get_numbers(self, group_id=-1):
        """Return list of numbers"""
        response = self.client.service.get_numbers(self.user, group_id)
        if "result" not in response or response["result"] != 0:
            raise SmsApiException("%d: %s" % (
                response.get("result", -1),
                response.get("description", ""),
            ))
        if "numbers" not in response:
            return []
        retlist = []
        for n in response["numbers"]:
            retlist.append({
                'name': n["name"],
                'number': n["number"],
                'group_id': n["group_id"],
            })
        return retlist

    def add_number(self, number, name, group_id=-1):
        """Add number"""
        num = self.client.factory.create('Number')
        num.number = str(number)
        num.name = name
        num.group_id = group_id

        response = self.client.service.add_number(self.user, num)
        if "result" in response and response["result"] == 0:
            return True
        raise SmsApiException("Couldn't add number")

    def delete_number(self, number, group_id=-1):
        """Delete number"""
        response = self.client.service.delete_number(self.user, number, group_id)
        if "result" in response and response["result"] == 0:
            return True
        raise SmsApiException("Couldn't delete number")


class SmsApi(SmsApiBaseObject):

    def get_points(self):
        """Get user points

        return:
        *result type int 0 = OK lub kod bledu
        *description type string opis bledu lub wykonanego dzialania
        *points type float
        """

        params = {'username': self.username, 'password': self.password}
        return self._executeSMSApi(self.client.service.get_points, params)

    def check_sms(self, id):
        """Check sent sms' by id received form send_sms(...)
        
        return:
        *result type int 0 = ok lub kod bledu
        *description type string opis bledu lub wykonanego dzialania
        *status - optional, unbounded;  type smsstatus
            *id type string, id wiadomosci
            *recipient type string, numer telefonu odbiorcy
            *sender type string, pole nadawcy
            *message type string, tresc wiadomosci
            *flash type int, wiadomosc flash 0/1
            *eco type int, wiadomosc eco 0/1
            *date_send type int, data odebrania sms'a przez serwis
            *status type int, raport doreczenia sms'a
            *date_submit type int, data wyslania sms'a
            *date_done type int, data doreczenia sms'a
        
        exmaple: to find out status of the sms having id received 
        with send_sms() execute:
        check_sms(id)['status']['status']
            
            """

        return self._executeSMSApi(self.client.service.get_sms_by_ids, {'client': self.user, 'ids': id})

    def send_sms(self, recipient, sender, message, eco=1, date_send=None,
            params=[], idx=None, no_unicode=0, datacoding=None,
            partner_id=None, test=0, priority=None, udh=None, flash=None):
        """Send SMS message

        return:
        *result type int 0 = OK lub kod bledu (Dodatek nr 2)
        *response - optional, unbounded, nillable;  type SMSIDO
            *id type string, ID wiadomosci wewnatrz system
            *phone type string, Numer telefonu
            *points type float, Ilosc pobranych punktow za wysylk
        *description type string, Opis bledu lub wykonanego dzialania
        *count type int, Ilosc wyslanych SMS'ow
        *points type float, Ilosc pobranych punktow za wysylke

        exmaple:to find out the id of sms execute
        send_sms(...)['response']['id']

        """
        sms = self.client.factory.create('SMS')
        sms.recipient = recipient
        sms.sender = sender
        sms.message = message
        sms.eco = 1 if eco else 0
        sms.params = params
        sms.idx = idx
        sms.single_message = 1
        sms.no_unicode = 1 if no_unicode else 0
        sms.datacoding = "bin" if datacoding else None
        sms.partner_id = partner_id
        sms.test = 1 if test else 0
        sms.priority = 1 if priority else 0
        sms.udh = udh
        sms.flash = flash
        sms.details = True

        if date_send:
            try:
                sms.date_send = time.mktime(date_send.timetuple())
            except Exception, e:
                raise SmsApiException(e)

        return self._executeSMSApi(self.client.service.send_sms,
                {'client': self.user, 'sms': sms})
