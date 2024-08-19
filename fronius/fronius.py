import requests
import json
import hashlib
import logging
import time
import os

logger = logging.getLogger('__main__')
logger.info(f'[Fronius] loading module ')

def hash_utf8(x):
    if isinstance(x, str):
        x = x.encode("utf-8")
    return hashlib.md5(x).hexdigest()

def strip_dict(original):
    #return unmodified original if its not a dict
    if not type(original) == dict:
        return original
    stripped_copy={}
    for key in original.keys():
        if not key.startswith('_'):
            stripped_copy[key]=original[key]
    return stripped_copy
    
TIMEOFUSE_CONFIG_FILENAME = 'timeofuse_config.json'
BATTERY_CONFIG_FILENAME = 'battery_config.json'

from .baseclass import InverterBaseclass
class FroniusWR(InverterBaseclass):
    def __init__(self, address, user, password,max_grid_charge_rate,max_pv_charge_rate) -> None:
        super().__init__()
        self.login_attempts=0
        self.address = address
        self.capacity = -1
        self.max_grid_charge_rate= max_grid_charge_rate 
        self.max_pv_charge_rate= max_pv_charge_rate 
        self.nonce = 0
        self.user = user
        self.password = password
        self.previous_config=self.get_battery_config()
        if not self.previous_config:
            raise RuntimeError(f'[Fronius] failed to load Battery config from Inverter at {self.address}')
        self.min_soc = self.previous_config['BAT_M0_SOC_MIN'] # in percent
        self.max_soc = self.previous_config['BAT_M0_SOC_MAX']
        
        self.get_time_of_use() #save timesofuse
        
    def get_SOC(self):
        path='/solar_api/v1/GetPowerFlowRealtimeData.fcgi'
        response = self.send_request(path)
        if not response:
            logger.error(f'[Fronius] Failed to get SOC. Returning default value of 99.0')
            return 99.0
        result = json.loads(response.text)
        soc = result['Body']['Data']['Inverters']['1']['SOC']
        return soc
    def get_free_capacity(self):
        current_soc=self.get_SOC()
        capa=self.get_capacity()
        free_capa=(self.max_soc-current_soc)/100*capa
        return free_capa
    
    def get_stored_energy(self):
        current_soc=self.get_SOC()
        capa=self.get_capacity()
        energy=(current_soc-self.min_soc)/100*capa
        return energy

    def get_max_capacity(self):
        return self.max_soc

    def get_usable_capacity(self):
        usable_capa=(self.max_soc-self.min_soc)/100*self.get_capacity()
        return usable_capa
        
    def get_battery_config(self):
        path='/config/batteries'
        response = self.send_request(path, auth=True)
        if not response:
            logger.error(f'[Fronius] Failed to get SOC. Returning empty dict')
            return {}
        result = json.loads(response.text)
        with open(BATTERY_CONFIG_FILENAME,'w') as f:
            f.write(response.text)
        return result
    def restore_battery_config(self):
        settings_to_restore=[
            'BAT_M0_SOC_MAX',
            'BAT_M0_SOC_MIN',
            'BAT_M0_SOC_MODE',
            'HYB_BM_CHARGEFROMAC',
            'HYB_EM_MODE',
            'HYB_EM_POWER',
            'HYB_EVU_CHARGEFROMGRID'
        ]
        settings={}
        for key in settings_to_restore:
            if key in self.previous_config.keys():
                settings[key]=self.previous_config[key]
            else:
                RuntimeError(f"Unable to restore settings. Parameter {key} is missing")
        path='/config/batteries'
        payload=json.dumps(settings)
        logger.info(f'[Fronius] Restoring previous battery configuration: {payload} ')
        response = self.send_request(path,method='POST',payload=payload, auth=True)
        if not response:
            raise RuntimeError(f'failed to restore battery config')
        
        response_dict=json.loads(response.text)
        expected_write_successes=settings_to_restore
        for expected_write_success in expected_write_successes:
            if not expected_write_success in response_dict['writeSuccess']:
                raise RuntimeError(f'failed to set {expected_write_success}')
        return response
    
    def set_allow_grid_charging(self, value:bool):
        if value:
            payload='{"HYB_EVU_CHARGEFROMGRID": true}'
        else:
            payload='{"HYB_EVU_CHARGEFROMGRID": false}'
        path='/config/batteries'
        response = self.send_request(path,method='POST',payload=payload, auth=True)
        response_dict=json.loads(response.text)
        expected_write_successes=['HYB_EVU_CHARGEFROMGRID']
        for expected_write_success in expected_write_successes:
            if not expected_write_success in response_dict['writeSuccess']:
                raise RuntimeError(f'failed to set {expected_write_success}')
        return response
    
    def set_wr_parameters(self, minsoc, maxsoc,allow_grid_charging,grid_power):
        """set power at grid-connection point negative values for Feed-In"""
        path='/config/batteries'
        if not type(allow_grid_charging) == bool:
            raise RuntimeError(f'Expected type: bool actual type: {type(allow_grid_charging)}')
        
        grid_power=int(grid_power)
        minsoc=int(minsoc)
        maxsoc=int(maxsoc)
        
        if not 0<=grid_power<=self.max_grid_charge_rate:
            raise RuntimeError(f'gridpower out of allowed limits {grid_power}')
        
        if minsoc>maxsoc:
            raise RuntimeError(f'Min SOC needs to be higher than Max SOC')
        
        if minsoc<self.min_soc:
            raise RuntimeError(f'Min SOC not allowed below {self.min_soc}')
        
        if maxsoc>self.max_soc:
            raise RuntimeError(f'Max SOC not allowed above {self.max_soc}')
                    
        parameters={'HYB_EVU_CHARGEFROMGRID':allow_grid_charging,
                    'HYB_EM_POWER':grid_power,
                    'HYB_EM_MODE':1,
                    'BAT_M0_SOC_MIN':minsoc,
                    'BAT_M0_SOC_MAX':maxsoc,
                    'BAT_M0_SOC_MODE':'manual'                    
                    }
        
        payload=json.dumps(parameters)
        logger.info(f'[Fronius] Setting battery parameters: {payload} ')
        
        response = self.send_request(path,method='POST',payload=payload, auth=True)
        if not response:
            logger.error(f'[Fronius] Failed to set parameters. No response from server')
            return response
        response_dict=json.loads(response.text)
        for expected_write_success in parameters.keys():
            if not expected_write_success in response_dict['writeSuccess']:
                raise RuntimeError(f'failed to set {expected_write_success}')
        return response
    
    def get_time_of_use(self):
        response= self.send_request('/config/timeofuse',auth=True)
        if not response:
            return None
        
        result=json.loads(response.text)['timeofuse']
        if not os.path.exists(TIMEOFUSE_CONFIG_FILENAME):
            with open(TIMEOFUSE_CONFIG_FILENAME,'w') as f:
                f.write(json.dumps(result))
        return result   
    
    def set_mode_avoid_discharge(self):
        timeofuselist= [{'Active': True, 
            'Power': 0, 
            'ScheduleType': 'DISCHARGE_MAX', 
            'TimeTable': {'End': '23:59', 'Start': '00:00'},
            'Weekdays': {'Fri': True, 'Mon': True, 'Sat': True, 'Sun': True, 'Thu': True, 'Tue': True, 'Wed': True}
        }]
        self.set_allow_grid_charging(False)
        return self.set_time_of_use(timeofuselist)

    def set_mode_allow_discharge(self):
        self.set_allow_grid_charging(False)
        if self.max_pv_charge_rate>0:
            timeofuselist= [{'Active': True, 
                'Power': self.max_pv_charge_rate, 
                'ScheduleType': 'CHARGE_MAX', 
                'TimeTable': {'End': '23:59', 'Start': '00:00'},
                'Weekdays': {'Fri': True, 'Mon': True, 'Sat': True, 'Sun': True, 'Thu': True, 'Tue': True, 'Wed': True}
            }]
            response = self.set_time_of_use(timeofuselist)
        else:
            response = self.set_time_of_use([]) #set empty time of use list to remove all rules
            
        return response
    
    def set_mode_force_charge(self,chargerate=500):
        #activate timeofuse rules
        if chargerate>self.max_grid_charge_rate:
            chargerate=self.max_grid_charge_rate
        timeofuselist= [{'Active': True, 
            'Power': chargerate, 
            'ScheduleType': 'CHARGE_MIN', 
            'TimeTable': {'End': '23:59', 'Start': '00:00'},
            'Weekdays': {'Fri': True, 'Mon': True, 'Sat': True, 'Sun': True, 'Thu': True, 'Tue': True, 'Wed': True}
        }]
        self.set_allow_grid_charging(True)
        return self.set_time_of_use(timeofuselist)
    
    def restore_time_of_use_config(self):
        try:
            with open(TIMEOFUSE_CONFIG_FILENAME,'r') as f:
                time_of_use_config_json=f.read()
        except OSError:
            logger.error(f'[Fronius] could not restore timeofuse config')
            return
        
        try:
            time_of_use_config=json.loads(time_of_use_config_json)
        except:
            logger.error(f'[Fronius] could not parse timeofuse config from {TIMEOFUSE_CONFIG_FILENAME}')
            return
        
        stripped_time_of_use_config=[]
        for listitem in time_of_use_config:
            new_item={}
            new_item['Active']=listitem['Active']
            new_item['Power']=listitem['Power']
            new_item['ScheduleType']=listitem['ScheduleType']
            new_item['TimeTable']={
                'Start':listitem['TimeTable']['Start'],
                'End':listitem['TimeTable']['End']
            }
            weekdays={}
            for day in ['Mon','Tue','Wed','Thu', 'Fri', 'Sat','Sun']:
                weekdays[day]=listitem['Weekdays'][day]
            new_item['Weekdays']=weekdays
            stripped_time_of_use_config.append(new_item)
        
        self.set_time_of_use(stripped_time_of_use_config)
        
         

    def set_time_of_use(self, timeofuselist):
        config={
            'timeofuse' : timeofuselist
        }
        payload=json.dumps(config)
        response= self.send_request('/config/timeofuse', method='POST',payload=payload,auth=True)
        response_dict=json.loads(response.text)
        expected_write_successes=['timeofuse']
        for expected_write_success in expected_write_successes:
            if not expected_write_success in response_dict['writeSuccess']:
                raise RuntimeError(f'failed to set {expected_write_success}')
        return response
    
    def get_capacity(self):
        if self.capacity >= 0:
            return self.capacity
        
        response = self.send_request('/solar_api/v1/GetStorageRealtimeData.cgi')
        if not response:
            logger.warn(f'[Fronius] capacity request failed. Returning default value')
            return 1000
        result = json.loads(response.text)
        capacity = result['Body']['Data']['0']['Controller']['DesignedCapacity']
        self.capacity = capacity
        return capacity

    def send_request(self,  path, method='GET',payload="", params=None, headers={}, auth=False):
        for i in range(3):
            url = 'http://' + self.address+ path
            fullpath = path
            if params:
                fullpath += '?' + \
                    "&".join(
                        [f'{k+"="+str(params[k])}' for k in params.keys()])
            if auth:
                headers['Authorization'] = self.get_auth_header(
                    method=method, path=fullpath)
            try:
                response = requests.request(method=method, url=url, params=params, headers=headers,data=payload)
                if response.status_code == 200:
                    return response
                elif response.status_code == 401: #unauthorized
                    self.nonce = self.get_nonce(response)
                    if self.login_attempts >=3:
                        logger.info('[Fronius] Login failed 3 times .. aborting')
                        raise RuntimeError('[Fronius] Login failed repeatedly .. wrong credentials?')
                    response = self.login()
                    if (response.status_code==200):
                        logger.info('[Fronius] Login successful')
                        self.login_attempts=0
                    else:
                        logger.info('[Fronius] Login failed')
                else:
                    raise RuntimeError(
                        f"Server {self.address} returned {response.status_code}")
            except requests.exceptions.ConnectionError as err:
                logger.error(f"[Fronius] Connection to Inverter failed on {self.address}. Retrying in 120 seconds")
                time.sleep(20)

                
        response=None
        return response
                
    def login(self):
        params = {"user": self.user}
        path='/commands/Login'
        self.login_attempts +=1
        return self.send_request(path, auth=True)
    
    def logout(self):
        params = {"user": self.user}
        path='/commands/Logout'
        response= self.send_request(path, auth=True)
        if not response:
            logger.warn('[Fronius] Logout failed. No response from server')
        if response.status_code==200:
            logger.info('[Fronius] Logout successful')
        else:
            logger.info('[Fronius] Logout failed')
        return response

    def get_nonce(self, response):
        #stupid API bug: nonce headers with different capitalization at different end points
        if 'X-WWW-Authenticate' in response.headers:
            auth_string = response.headers['X-WWW-Authenticate']
        elif 'X-Www-Authenticate' in response.headers:
            auth_string = response.headers['X-Www-Authenticate']
        else:
            auth_string=""
        
        auth_list = auth_string.replace(" ", "").replace('"', '').split(',')
        auth_dict = {}
        for item in auth_list:
            key, value = item.split("=")
            auth_dict[key] = value
        return auth_dict['nonce']

    def get_auth_header(self, method, path):
        nonce = self.nonce
        realm = 'Webinterface area'
        ncvalue = "00000001"
        cnonce = "NaN"
        user=self.user
        password=self.password
        if len(self.user)<4:
            raise RuntimeError("User needed for Authorization")
        if len(self.password)<4:
            raise RuntimeError("Password needed for Authorization")
            
        A1 = f"{user}:{realm}:{password}"
        A2 = f"{method}:{path}"
        HA1 = hash_utf8(A1)
        HA2 = hash_utf8(A2)
        noncebit = f"{nonce}:{ncvalue}:{cnonce}:auth:{HA2}"
        respdig = hash_utf8(f"{HA1}:{noncebit}")
        auth_header = f'Digest username="{user}", realm="{realm}", nonce="{nonce}", uri="{path}", algorithm="MD5", qop=auth, nc={ncvalue}, cnonce="{cnonce}", response="{respdig}"'
        return auth_header
    def __del__(self):
        self.restore_battery_config()
        self.restore_time_of_use_config()
        self.logout()


