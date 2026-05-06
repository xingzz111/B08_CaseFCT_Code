import threading
from threading import Thread
import json
import time
import zmq
import traceback
from xml.etree import ElementTree

from prmcommon.network.http.http_client import HttpClient
from prmcommon import constant
from prmcommon.constant import console_log_highlight, console_log_warning, console_log_error

from rtSque.tinyrpc import ZmqPublisher
from rtSque.tinyrpc import NoOpPublisher

# import mes.mes_config
from mes import mes_config

class MesClient(HttpClient):

    TIME_OUT = 10

    OP_ID = 'A001'

    def __init__(self, publisher=None, params_prefix='strjson'):
        _header = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept-Encoding': 'gzip, deflate'
        }
        print('MesClient-publisher:{}'.format(publisher))
        super(MesClient, self).__init__(mes_config.MES_HOST, _header, publisher)

        self.params_prefix = params_prefix

    def get_base_params(self):
        _base_params = dict()
        _base_params.setdefault('VERSION', mes_config.MES_VERSION)
        _base_params.setdefault('JIG_NO', mes_config.MES_JIG_NO)
        _base_params.setdefault('TERMINAL_NAME', constant.TERMINAL_NAME)
        _base_params.setdefault('EMPNO', self.OP_ID)

        return _base_params

    # method: GET/POST
    # params: type dict/string/bytes
    # return: tuple(result, response, error_msg, total_time)
    def hrequest(self, url, method, params, timeout=None):

        _result = False
        _response = None
        _error_msg = ''
        _total_time = 0

        if not isinstance(params, dict):
            _result = False
            _response = None
            _error_msg = 'HTTP(MES)({}) request params({}) type error'.format(url, str(params))
            self.log('HTTP({}) request params({}) type error'.format(url, str(params)))
            console_log_error(_error_msg)
        else:

            _data = self.get_base_params()
            _data.update(params)

            _data_json_str = json.dumps(_data)

            _params_json_str = '{}={}'.format(self.params_prefix, _data_json_str)

            console_log_highlight('MesClient-hrequest-_data:{}'.format(_params_json_str))

            try:
                _result, _response, _error_msg, _total_time = \
                    super(MesClient, self).hrequest(url, method, _params_json_str, timeout)
                if _result:
                    _json = ElementTree.fromstring(str(_response)).text
                    console_log_highlight('HTTP(MES)({}) response:{}'.format(url, _json))
                    self.log('HTTP({}) response:{}'.format(url, _json))
                    _response = json.loads(_json)
                    _response = MesClient._normalize_obj(_response)
                else:
                    console_log_error('MesClient-hrequest-error:{}'.format(_error_msg))

            except Exception as e:
                _error_msg = 'HTTP(MES)({}) Request Exception: ({}) {}'.format(url, _params_json_str, e)
                self.log('HTTP(MES)({}) Request Exception: ({}) {}'.format(url, _params_json_str, e))
                print(traceback.format_exc())
                _result = False
                # return {'RESULT': 'FAIL', 'RESULT_INFO': 'Network anomaly'}

        return _result, _response, _error_msg, _total_time

    @staticmethod
    def _contains_cjk(s):
        for ch in s:
            o = ord(ch)
            if 0x4E00 <= o <= 0x9FFF:
                return True
        return False

    @staticmethod
    def _maybe_fix_mojibake(s):
        if not isinstance(s, str) or not s:
            return s
        if MesClient._contains_cjk(s):
            return s
        has_latin1_ext = any(0x00C0 <= ord(ch) <= 0x00FF for ch in s)
        if not has_latin1_ext:
            return s
        for enc in ("gb18030", "gbk"):
            try:
                fixed = s.encode("latin1").decode(enc)
                if MesClient._contains_cjk(fixed):
                    return fixed
            except Exception:
                continue
        return s

    @staticmethod
    def _normalize_obj(obj):
        if obj is None:
            return None
        if isinstance(obj, str):
            return MesClient._maybe_fix_mojibake(obj)
        if isinstance(obj, list):
            return [MesClient._normalize_obj(i) for i in obj]
        if isinstance(obj, tuple):
            return tuple(MesClient._normalize_obj(i) for i in obj)
        if isinstance(obj, dict):
            new = {}
            for k, v in obj.items():
                nk = MesClient._normalize_obj(k) if isinstance(k, str) else k
                new[nk] = MesClient._normalize_obj(v)
            return new
        return obj

    def log(self, msg):
        print('self.publisher =', self.publisher)
        if self.publisher:
            self.publisher.publish('[MES HttpClent] ' + str(msg))


def set_op_id(op_id):
    MesClient.OP_ID = op_id

if __name__ == '__main__':

    host = "http://127.0.0.1:5000/"

    payload = {
        'cmd': 'UOP',
        'sn': 'H5R0253003B02Q31T',
        'Station_ID': 'ITKS_E03-2FT-15A_2_AE-16'
    }

    # ctx = zmq.Context()
    # key = 'mes'
    # if host:
    #     publisher = ZmqPublisher(ctx, host, 'dut0'.encode('utf-8'))
    # else:
    #     publisher = NoOpPublisher()

    _http_client = MesClient(host)
    response = _http_client.post('log', payload)

    print('response:{}'.format(response))

#     _xml_str = """
# <string xmlns="MES_WEBSERVICE">{"COMMAND":"CheckData","SERIAL_NUMBER":"TESTSN-015","VERSION":"V1.0","TERMINAL_NAME":"E4_2F_B01_BMBL_BIST_01","RESULT":"FAIL","RESULT_INFO":"NO SN"}</string>
#     """
#
#     _dom = ElementTree.fromstring(_xml_str)
#     print(_dom.text)
#     print(type(_dom.text))
