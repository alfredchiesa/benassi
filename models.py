from django.db import models
from django.conf import settings
from socket import socket
import datetime, struct, ssl, binascii, json, base64
from django.contrib.auth.models import User

APPLE_LIVE = "gateway.push.apple.com"
APPLE_LIVE_FB = "feedback.push.apple.com"
APPLE_SANDBOX = "gateway.sandbox.push.apple.com"
APPLE_SANDBOX_FB = "feedback.sandbox.push.apple.com"

class Cert(models.Model):
    user = models.ForeignKey(User)
    _live = models.TextField(blank=True)
    _dev = models.TextField(blank=True)

    def set_live(self, cert):
        self._live = base64.encodestring(cert)

    def get_live(self):
        return base64.decodestring(self._live)

    def set_dev(self, cert):
        self._dev = base64.encodestring(cert)

    def get_dev(self):
        return base64.decodestring(self._dev)

    live = property(get_live, set_live)
    dev = property(get_dev, set_dev)



class Device(models.Model):
    udid = models.CharField(blank=False, max_length=64)
    last_push = models.DateTimeField(blank=True, default=datetime.datetime.now)
    test_device = models.BooleanField(default=False)
    ios = models.BooleanField(default=True)
    notes = models.CharField(blank=True, max_length=100)
    feedback = models.BooleanField(default=False)

    class Admin:
        list_display = ('',)
        search_fields = ('',)

    def _getPushServer(self):
        if self.test_device and self.ios:
            return APPLE_SANDBOX
        elif self.ios:
            return APPLE_LIVE
        elif self.test_device and not self.ios:
            raise NotImplementedError
        else:
            raise NotImplementedError

    def _getPushCertificate(self):
        if self.test_device:
            return settings.APPLE_SANDBOX_CERT
        else:
            return settings.APPLE_LIVE_CERT

    def send_push(self, alert, badge=0, sound="chime",
                        custom_params={}, action_loc_key=None, loc_key=None,
                        loc_args=[], passed_socket=None):
        aps_payload = {}

        alert_payload = alert
        if action_loc_key or loc_key or loc_args:
            alert_payload = {'body' : alert}
            if action_loc_key:
                alert_payload['action-loc-key'] = action_loc_key
            if loc_key:
                alert_payload['loc-key'] = loc_key
            if loc_args:
                alert_payload['loc-args'] = loc_args

        aps_payload['alert'] = alert_payload

        if badge:
            aps_payload['badge'] = badge

        if sound:
            aps_payload['sound'] = sound

        payload = custom_params
        payload['aps'] = aps_payload

        # This ensures that we strip any whitespace to fit in the
        # 256 bytes
        s_payload = json.dumps(payload, separators=(',',':'))

        # Check we're not oversized
        if len(s_payload) > 256:
            raise OverflowError, 'The JSON generated is too damn big man: %d - *** "%s" ***' % (len(s_payload), s_payload)

        fmt = "!cH32sH%ds" % len(s_payload)
        command = '\x00'
        msg = struct.pack(fmt, command, 32, binascii.unhexlify(self.udid), len(s_payload), s_payload)

        if passed_socket:
            passed_socket.write(msg)
        else:
            s = socket()
            c = ssl.wrap_socket(s,
                                ssl_version=ssl.PROTOCOL_SSLv3,
                                certfile=self._getPushCertificate())
            c.connect((self._getPushServer(), 2195))
            c.write(msg)
            c.close()

        return True

    def __unicode__(self):
        return u"The Device UDID is: %s" % self.udid

def sendMessageToPhoneGroup(phone_list, alert, badge=0, sound="chime",
                            custom_params={}, action_loc_key=None, loc_key=None,
                            loc_args=[], sandbox=False):
    host_name = None
    cert_path = None

    if sandbox:
        host_name = settings.APPLE_SANDBOX
        cert_path = settings.APPLE_SANDBOX_CERT
    else:
        host_name = settings.APPLE_LIVE
        cert_path = settings.APPLE_LIVE_CERT

    s = socket()
    c = ssl.wrap_socket(s,
                        ssl_version=ssl.PROTOCOL_SSLv3,
                        certfile=cert_path)
    c.connect((host_name, 2195))

    for phone in phone_list:
        if phone.test_device == sandbox:
            phone.send_push(alert, badge, sound, custom_params,
                            action_loc_key, loc_key, loc_args, c)

    c.close()

def doFeedbackLoop(sandbox = False):
    #doesn't do anything yet, but should mark feedback for returned items
    raise NotImplementedError

    if sandbox:
        host_name = settings.APPLE_SANDBOX_FB
        cert_path = settings.APPLE_SANDBOX_CERT
    else:
        host_name = settings.APPLE_LIVE_FB
        cert_path = settings.APPLE_LIVE_CERT

    s = socket()
    c = ssl.wrap_socket(s,
                        ssl_version=ssl.PROTOCOL_SSLv3,
                        certfile=settings.IPHONE_APN_PUSH_CERT)
    c.connect((settings.IPHONE_FEEDBACK_HOST, 2196))

    full_buf = ''
    while 1:
        tmp = c.recv(38)
        print tmp
        if not tmp:
            break
        else:
            full_buf += tmp

    c.close()
