from pylab.manager import Logger
import numpy as np
import matplotlib.pyplot as plt
import os, glob, time, copy, math, datetime
import pickle
import json
import csv
from pylab.instruments import PumpPSD8
from pylab.instruments import Valco_valve
try:
    from transient_emission import Transient_Emission
    from absorption_and_PL import Abs_PL
    from proc_image import ImageHandler
except:
    from .transient_emission import Transient_Emission
    from .absorption_and_PL import Abs_PL
    from .proc_image import ImageHandler
"""
Automatic optical measurement with flow selector
"""

today = datetime.date.today()
today_formatted = today.strftime("%Y%m%d")

filedir = os.path.dirname(os.path.realpath(__file__))
config_file = '%s/.config_AutoOpt.dat' %filedir

log_file = '%s/log/%s.txt' %(filedir, today_formatted)


## settings
ml = 1e-3

buffer_volume = 0.025*ml
loop_to_pump  = 0.04*ml # (under)
selector_to_pump  = 0.05*ml # (under)

flow_cells = {
    'TE' : {
        'name' : 'flow_cell',
        'to_cell_under' : 0.46*ml,
        'to_cell_over' : 0.51*ml
    },
    'absorption' : {
        'name' : 'flow_cell_abs',
        'to_cell_under' : 0.245*ml,
        'to_cell_over' : 0.28*ml       
    },
    'PL' : {
        'name' : 'flow_cell_PL',
        'to_cell_under' : 0.35*ml,
        'to_cell_over' : 0.40*ml
    } 
}

for val in flow_cells.values():
    val['cell_volume'] = round(val['to_cell_over'] - val['to_cell_under'] + 2*buffer_volume, 6)


pump_setting =   { 
            "visa": "ASRL2::INSTR",
            "addr": 0,
            "syringe_volume": 1E-3,
            "init_valve": 8,
            "ports": {
                "vial": 1,
                "ACN": 2,
                "flow_cell_PL": 3,
                "flow_cell_abs" : 4,
                "flow_cell": 5,
                "air":6,
                "waste": 7,
                "valve": 8,
            }
}

class absorption(object):
    def __init__(self):
        self.attrs = ['reference', 'sample', 'transmittance', 'absorbance', 'max', 'lambda_max', 'end_index', 'end_wavelength']
        # self.reference = None
        # self.sample = None
        # self.transmittance = None
        # self.absorbance = None
        # self.max = None
        # self.lambda_max = None
        # self.end_index = None
        # self.end_wavelength = None
    
    def _to_dict(self):



class Optical_measurements():

    def __init__(self, TE=True, AbsPL=True, Pump=True, logger = False):

        if logger:
            self.log = Logger(stdout=True, logfile=log_file, pause=False, time_format='({:%Y-%m-%d %H:%M:%S})')
        else:
            self.log = Logger(stdout=True, logfile=None, pause=False, time_format='({:%Y-%m-%d %H:%M:%S})')

        self.config = self._load_config(config_file)
        
        if Pump:
            self.pump = PumpPSD8(**pump_setting)
            self.pump.set_velocity(1000)

            self.update_valve_status('free')

        self.AP = Abs_PL(led_power=self.config['PL']['led_power'], correction_datafile= self.config['data_processing']['correction_datafile'], device=AbsPL)
        self.TE = Transient_Emission(device = TE, DB = False)
        if TE:         
            self.TE.detector_on()        
        
        self.IM = ImageHandler()
        

    def close(self):
        self.log('closing device')
        if self.TE.device:
            self.TE.detector_off()
            self.TE.laser_off()
        if self.AP.device:
            self.AP.led_off()
            self.AP.lamp_off()
        self.log(self.AP.lamp.check_status())
        self.log(self.AP.led_365.get_state())

    #load setting#########################
    def _load_config(self, config_file):
        
        with open(config_file) as content:
            config = json.loads(content.read())

        for val in config.values():
            for key in val.keys():
                if val[key] == 'True':
                    val[key] = True
                elif val[key] == 'False':
                    val[key] = False
                elif val[key] == 'None':
                    val[key] = None
        self.log('load %s' %config_file)
        return config


    def _load_setting(self, **kwargs):
        import copy
        config = copy.deepcopy(self.config)
        setting = {}

        for val in config.values():
            for key in val.keys():
                if key in kwargs.keys():
                    val[key] = kwargs[key]
                setting[key] = val[key]

        return config, setting

    #overwrite pump methods###################
    def draw(self, valve, volume, velocity):
        self.pump.set_velocity(velocity)
        self.pump.draw(volume, valve = valve)

    def dispense(self, valve, volume, velocity):
        self.pump.set_velocity(velocity)
        self.pump.dispense(volume, valve = valve)

    def draw_full(self, valve, velocity):
        self.pump.set_velocity(velocity)
        self.pump.draw_full(valve = valve)

    def dispense_all(self, valve, velocity):
        self.pump.set_velocity(velocity)
        self.pump.dispense_all(valve=valve)

    def draw_and_dispense(self, from_valve, to_valve, volume, draw_velocity, dispense_velocity):

        while volume >= self.pump.syringe_volume:
            volume -= self.pump.syringe_volume
            self.draw_full(from_valve, draw_velocity)
            self.dispense_all(to_valve, dispense_velocity)

        self.draw(from_valve, volume, draw_velocity)
        self.dispense(to_valve, volume, dispense_velocity)


    def measure_line(self, line, fill=None, volume=1*ml, step = 0.01*ml):
        if fill:
            self.draw(fill, volume, 1000)
            action = self.pump.dispense
        else:
            action = self.pump.draw

        c = ''
        volume = 0
        while c != 'c':
            action(volume=step, valve=line)
            volume += step *1000
            c = input(f'{volume:.3f}')

        self.pump.dispense_all('waste')

    #system washing functions#################################
    def cell_wash(self, cells, volume, repeat):
        for cell in cells:
            self.log('Wash %s' %cell)
            for _ in range(repeat):
                self.draw_and_dispense('ACN', cell, volume, draw_velocity=500, dispense_velocity=1000)


    def vial_wash(self, volume, repeat):
        self.log('Wash vial')
        for _ in range(repeat):
            self.draw_and_dispense('ACN', 'vial', volume, draw_velocity = 1000, dispense_velocity = 1000)
            self.draw_and_dispense('vial', 'waste', 1*ml, draw_velocity = 1000, dispense_velocity = 2000)

    def collector_wash(self, volume, repeat, collector_num):

        self.open_valves()

        self.log(f'Wash collector {collector_num:.0f}')
        self.selector.move_to(collector_num)
        self.valve.move_to('A')
        for _ in range(repeat):
            self.draw_and_dispense('ACN', 'valve', volume, draw_velocity = 1000, dispense_velocity = 1000)
            self.draw_and_dispense('valve', 'waste', 1*ml, draw_velocity = 1000, dispense_velocity = 2000)
        self.draw_and_dispense('valve', 'waste', 1*ml, draw_velocity = 2000, dispense_velocity = 2000)
        self.selector.move_to(1)

        self.update_vial_status(collector_num, True)
        self.close_valves()


    #deal with vial status#################################
    def update_vial_status(self, vial_number, status):
        fname = '%s/available_vials.pkl' %self.config['data_path']['status']
        with open (fname, 'rb') as f:
            collector_status = pickle.load(f)
        collector_status[str(vial_number)] = status
        with open (fname, 'wb') as f:
            pickle.dump(collector_status, f)
        self.log('update vial status : vial %s %s' %(vial_number, status))


    def check_vial_status(self):
        fname = '%s/available_vials.pkl' %self.config['data_path']['status']
        with open (fname, 'rb') as f:
            print(pickle.load(f))


    #handle valve connection#################################
    def update_valve_status(self, status):
        fname = '%s/valve_status_characterization.pkl' %self.config['data_path']['status']
        with open (fname, 'wb') as f:
            pickle.dump(status, f)


    def check_valve_status(self):
        fname = '%s/valve_status_HPLCMS.pkl' %self.config['data_path']['status']
        with open (fname, 'rb') as f:
            status = pickle.load(f)
            print('HPLCMS_valve_status : %s' %status)
        return status


    def open_valves(self):
        while True:
            if self.check_valve_status() == 'free':
                self.valve = Valco_valve('visa://10.22.1.20/ASRL4::INSTR', dev_id = 0, mode = 1, position = 'A')
                self.selector = Valco_valve('visa://10.22.1.20/ASRL17::INSTR', dev_id = 0, mode = 3, position = 1)
                self.update_valve_status('busy')
                self.log('valve connection opened')
                break
            else : 
                print('Valves are busy for HPLCMS. Wait a moment\n***********************')
                time.sleep(5)


    def close_valves(self):
        self.valve.move_to('B')
        self.selector.move_to(1)
        self.valve.close_device()
        self.selector.close_device()
        self.update_valve_status('free')
        del self.selector, self.valve
        self.log('valve connection closed')


    #transfer solutions#################################
    def fill_reference(self, water_ratio, measurements):

        num = len([measurement for measurement in measurements if measurement == 'absorption' or measurement == 'PL'])

        if water_ratio == 0 or num == 0:
            pass
        else:
            self.open_valves()
            self.log('mixing reference solution')
            self.draw_and_dispense('ACN', 'vial', 0.5 * num * (1-water_ratio)*ml, draw_velocity = 1000, dispense_velocity = 1000)
            #draw water
            self.selector.move_to(1)
            self.valve.move_to('B')
            self.draw_and_dispense('valve', 'waste', 0.3*ml, draw_velocity=1000, dispense_velocity=1000) #discard tube volume
            self.draw_and_dispense('valve', 'vial', 0.5 * num * water_ratio*ml, draw_velocity = 1000, dispense_velocity = 300)
            self.valve.move_to('A')

            for _ in range(2): #mixing
                self.draw_and_dispense('vial', 'vial', 1*ml, draw_velocity = 300, dispense_velocity = 300)
            
            if 'absorption' in measurements:
                self.log('Sending reference solution to absorption cell')
                self.draw_and_dispense('vial', 'flow_cell_abs', 0.5*ml, draw_velocity = 300, dispense_velocity = 300)
            if 'PL' in measurements:
                self.log('Sending reference solution to PL cell')
                self.draw_and_dispense('vial', 'flow_cell_PL', 0.5*ml, draw_velocity = 300, dispense_velocity = 300)
            self.close_valves()


    def collect_sample_from_valve(self, sample_volume, collector_num, setting):

        self.open_valves() #initialze valve at A and 1

        self.selector.move_to(1)

        self.log('washing selector to pump line with solvent {timestamp}')
        self.draw_and_dispense('ACN', 'valve', 0.3*ml, setting['dilution_draw_velocity'], setting['dilution_dispense_velocity'])        

        self.selector.move_to(6) #air

        self.log('Discard selector to pump volumes')
        self.draw_and_dispense('valve', 'waste', 0.3*ml, setting['dilution_draw_velocity'], setting['dilution_dispense_velocity'])


        self.log(f'Switch selector to position {collector_num:0f}')
        self.selector.move_to(collector_num)

        self.log(f'Draw {sample_volume*1000:.3f} ml of sample')
        self.draw_and_dispense('valve', 'vial', 1*ml, setting['dilution_draw_velocity'], setting['dilution_dispense_velocity'])
        
        #######
        # self.draw('valve', 1*ml, setting['dilution_draw_velocity'])
        # input('pause')
        # self.dispense_all('waste', setting['dilution_dispense_velocity'])
        #########
        
        #self.draw_and_dispense('valve', 'vial', 0.5*ml, setting['dilution_draw_velocity'], setting['dilution_dispense_velocity'])

        self.log(f'Switch selector to position 1')  

        self.close_valves() #close valves at B and 1


    def sample_dilution(self, sample_volume, dilution, setting):

        if dilution <= 1:
            raise Exception('dilution should be larger than 1')

        self.log(f'Draw {sample_volume*(dilution - 1)*1000:.3f} ml of solvent and mix in vial')
        self.draw_and_dispense('ACN', 'vial', sample_volume*(dilution - 1), setting['dilution_draw_velocity'], setting['dilution_dispense_velocity'])
        for _ in range(2):
            self.draw_and_dispense('vial', 'vial', sample_volume * dilution *2, setting['dilution_draw_velocity'], setting['dilution_dispense_velocity']) # mix 3 times


    def send_sample_to_cell(self, cell, draw_velocity = 500, dispense_velocity = 1000):

        flow_cell = flow_cells[cell]
        volume = flow_cell['cell_volume']

        #make flow cell empty
        self.log('Emplying the flow cell {timestamp}')
        self.pump.draw_and_dispense('air', flow_cell['name'], 0.5*ml, velocity=1000) #better not to draw solvent to the pump
        self.pump.draw_and_dispense('air', flow_cell['name'], 1*ml, velocity=2000) #to prevent unintentioanl dilution
        #self.pump.draw_and_dispense(flow_cell['name'], 'waste', 1*ml, velocity=2000) #to prevent unintentioanl dilution

        self.log(f'Send {volume/ml:.3f} ml of solution to flow cell')
        draw_volume = min(1*ml, volume *3)
        self.draw('vial', draw_volume , draw_velocity)

        self.dispense('vial', draw_volume - volume, dispense_velocity)
        self.dispense_all(flow_cell['name'], dispense_velocity)

        #send sample to the flowcell
        self.draw_and_dispense('air', flow_cell['name'], flow_cell['to_cell_under']- buffer_volume, 500, dispense_velocity)


    def collect_sample_from_cell(self, cell, draw_velocity = 500, dispense_velocity = 1000):
        
        flow_cell = flow_cells[cell]
        volume = flow_cell['cell_volume']

        self.log(f'Collect {volume/ml:.3f} ml of solution to flow cell')
        self.draw(flow_cell['name'], flow_cell['to_cell_over'] + buffer_volume *2, draw_velocity)
        #self.draw_full(flow_cell['name'], draw_velocity)
        self.dispense_all('vial', dispense_velocity)


    #process measurement results#################################
    def save_data(self, fname, data):
        np.savetxt(fname, data, delimiter=',', header='wl (nm), abs (%), pl (and abs/pl pair repeats)')


    #TODO time trace
    def write_result_csv(self, fname, results):

        if results['absorption'] == None and results['PL'] == None:
            return

        header1 = []
        header2 = []
        stats = []

        d = []

        if results['absorption'] != None:
            header1.extend(['abs_max', 'abs_lambda_max'])
            stats.extend([results['absorption']['max'], results['absorption']['lambda_max'] ])
            if results['absorption']['end_wavelength']:
                header1.extend(['abs_end'])
                stats.extend([results['absorption']['end_wavelength']])
            header2.extend(['wavelength/nm', 'abs_ref', 'abs_sample', 'transmittance', 'absorbance'])
            d.extend([results['absorption']['reference'][0], 
                        results['absorption']['reference'][1], 
                        results['absorption']['sample'][1], 
                        results['absorption']['transmittance'][1], 
                        results['absorption']['absorbance'][1]])
            
        if results['PL'] != None:
            header1.extend(['uv_ref(W)', 'uv_absorption(W)', 'uv_absorbance_maintenance','uv_absorbance_maintenance(at_1min)', 'degradation_rate(s-1)', 'PL_max','PL_lambda_max', 'relative_QY'])
            stats.extend([results['uv']['reference'], 
                          results['uv']['absorption'], 
                          results['uv']['absorbance_maintenance'],
                          results['uv']['absorbance_maintenance(at_1min)'],
                          results['uv']['degradation_rate'],
                          results['PL']['max'], 
                          results['PL']['lambda_max'], 
                          results['PL']['relative_QY']])
            if 'max_gain_factor' in results['PL'].keys():
                header1.extend(['max_gain_factor(cm2 s)'])
                stats.extend([results['PL']['max_gain_factor']])
            header2.extend(['wavelength/nm', 'PL(energy/s/nm)', 'PL(photons/s/nm)', 'PL(photons/s/Hz)', 'gain_factor(cm2 s)'])
            d.extend([results['PL']['energy'][0], 
                        results['PL']['energy'][1], 
                        results['PL']['photons'][1],
                        results['PL']['freq_spectrum'][1],
                        results['PL']['gain_spectrum'][1]])

        with open(fname, 'w', newline = '') as f:

            writer = csv.writer(f)
            writer.writerow(header1)
            writer.writerow(stats)
            d = np.transpose(np.asarray(d))
            writer.writerow(header2)
            writer.writerows(d)
        
        print('%s was saved' %fname)



    def abspl_result_plots(self, fname, results):
        #absortpion spectrum
        if results['absorption'] != None:
            text = 'abs_max : {:.4f} ({:.1f} nm)'.format(results['absorption']['max'], results['absorption']['lambda_max'])
            if results['absorption']['end_wavelength']:
                text = text + '\nabs_end : {:.1f} nm'.format(results['absorption']['end_wavelength'])
            self.AP.result_plot(results['absorption']['absorbance'], 'Absorbance', text=text, xrange = [300,800], show_plot=False, save_filename='%s_absorption_spactrum.png' %fname)
        #PL spectrum
        if results['PL'] != None:
            text = 'PL_max : {:.4f} ({:.1f} nm)\nabsorbed_power : {:.3f} mW\nrelative_QY : {:.3f}'.format\
                           (results['PL']['max'],results['PL']['lambda_max'],results['uv']['absorption']*1000,results['PL']['relative_QY'])
            if results['uv']['absorbance_maintenance'] is not None:
                text = text + '\nuv_absorbance_maintenance(%) : {:.2f}\nuv_absorbance_maintenance_1min(%) : {:.2f}\ndegradation_rate(s-1) : {:.5f}'.format\
                            (results['uv']['absorbance_maintenance']*100, results['uv']['absorbance_maintenance(at_1min)']*100,results['uv']['degradation_rate'])

            self.AP.result_plot(results['PL']['energy'], 'Intensity/ (energy/s/nm)', text = text,\
                                                                xrange = [300,800], show_plot=False, save_filename='%s_PL_spactrum.png' %fname)
            self.AP.result_plot(results['PL']['gain_spectrum'], 'gain factor/ (cm2 s)', text = None,\
                                                                xrange = [300,800], show_plot=False, save_filename='%s_PL_gain_spactrum.png' %fname)
            self.AP.plot_time_trace(results['uv'], results['PL'], show_plot=False, save_filename='%s_time_trace.png' %fname)
        #abs/PL spectrum
        if results['absorption'] != None and results['PL'] != None:
            self.AP.Abs_PL_plot(results['absorption']['absorbance'], results['PL']['energy'], text = None,\
                                                                xrange = [300,800], show_plot=False, save_filename='%s_Abs_PL_spactrum.png' %fname)
            if 'max_gain_factor' in results['PL'].keys():
                text = 'max_gain_factor(cm2 s) :\n {:.3e} ({:.1f} nm)'.format(results['PL']['max_gain_factor'], results['PL']['max_gain_wavelength'])
            else:
                text = None
            self.AP.Abs_PL_plot(results['absorption']['absorbance'], results['PL']['gain_spectrum'], text = text, xrange = [300,800], 
                                        ylabel = 'Nomalized Abs. and gain_factor.', show_plot=False, save_filename='%s_Abs_PL_gain_spectrum.png' %fname)


    def _find_maximum_gain(self, gain_spectrum , absorption_end_index, calc_range = [300,800]):

        l_index, u_index = self.AP._to_index_range(gain_spectrum[0], calc_range)
        l_index = max(l_index, absorption_end_index)

        spectrum = gain_spectrum[:, l_index:u_index+1]

        max_gain = np.max(spectrum[1])
        max_gain_wavelength = spectrum[0][np.argmax(spectrum[1])]
        return max_gain, max_gain_wavelength


    def join_images(self, fname, filelist):
        if len(filelist) > 1:
            self.IM.tile_img(h_num = 3, save_filename = '%s.png' %fname, mergin = [0,0,0,0], del_files=True, filelist=filelist)


    ###manual measurements#########################################
    def measure_PL_manual(self, fname, sample_info = None, **kwargs):

        config, setting = self._load_setting(**kwargs)

        results = {'uv' : None,  'absorption' : None, 'PL' :  None,  'TE' : None, 'metadata' : config}

        input('Please inject reference to the cell')

        #measure reference
        self.log('Measure reference uv power {timestamp}')
        uv_reference = self.AP.measure_uv_power(counts = setting['uv_average'], led_power = setting['led_power'])


        input('Please inject the sample to the cell')

        self.log('Adjust PL exposure {timestamp}')
        PL_exposure = self.AP.adjust_PL_exposure(setting['PL_initial_exposure'], setting['PL_max_exposure'], setting['PL_target_intensity'],\
                                                                        setting['led_power'], filter_size=setting['filter_size'], average = 5)
        self.log('Measure PL dark spectrum {timestamp}')
        self.AP.measure_dark_spectrum(20, PL_exposure, filter_size=setting['filter_size'],  do_plot=False) #dark for PL
        self.log('Measure PL spectrum {timestamp}')
        res = self.AP.measure_PL_uv(setting['PL_average'],  PL_exposure,  led_power = setting['led_power'],\
                                    filter_size = setting['filter_size'], dark_correction = True, spectral_correction = True, do_plot = False)

        #calculations
        uv, PL = self.AP.PL_uv_analysis(res, uv_reference, PL_exposure, setting['PL_calc_range'])
        PL['exposure'] = PL_exposure

        results['uv'] = uv
        results['PL'] = PL

        if sample_info:
            results['metadata']['sample'] = sample_info

        if fname:
            self.AP.save_pkl(fname + '.pkl', results)
            self.write_result_csv(fname + '_AbsPL.csv', results)
            self.abspl_result_plots(fname, results)

            self.join_images(fname, glob.glob('%s*.png' %fname))


        input('Measurement done. Please wash the cell')

        return uv, PL


    #measurement fuctions#################################
    def measure_PL(self, setting):

        results = {}

        #measure reference
        self.log('Measure reference uv power {timestamp}')
        uv_reference = self.AP.measure_uv_power(counts = setting['uv_average'], led_power = setting['led_power'])

        self.send_sample_to_cell(cell = 'PL', draw_velocity=setting['PL_draw_velocity'], dispense_velocity=setting['PL_dispense_velocity'])

        # need sometime until the solution reaches equiliblium (bubble??)
        print('waiting %s s for equibliration' %setting['PL_equibliration_time'])
        time.sleep(setting['PL_equibliration_time']) 


        self.log('Adjust PL exposure {timestamp}')
        PL_exposure = self.AP.adjust_PL_exposure(setting['PL_initial_exposure'], setting['PL_max_exposure'], setting['PL_target_intensity'],\
                                                                        setting['led_power'], filter_size=setting['filter_size'], average = 5)
        self.log('Measure PL dark spectrum {timestamp}')
        self.AP.measure_dark_spectrum(20, PL_exposure, filter_size=setting['filter_size'],  do_plot=False) #dark for PL
        self.log('Measure PL spectrum {timestamp}')
        results = self.AP.measure_PL_uv(setting['PL_average'],  PL_exposure,  led_power = setting['led_power'],\
                                    filter_size = setting['filter_size'], dark_correction = True, spectral_correction = True, do_plot = False)

        #calculations
        uv, PL = self.AP.PL_uv_analysis(results, uv_reference, PL_exposure, setting['PL_calc_range'])
        PL['exposure'] = PL_exposure

        # input('pause')
        self.collect_sample_from_cell(cell = 'PL', draw_velocity=setting['PL_draw_velocity'], dispense_velocity=setting['PL_dispense_velocity'])

        return uv, PL


    def measure_absorption(self, setting):

        absorption = {}

        #measure reference
        self.log('Measure absorption reference {timestamp}')
        self.AP.measure_dark_spectrum(setting['dark_average'], setting['abs_exposure'], filter_size=setting['filter_size'],  do_plot=False)
        absorption['reference'] = self.AP.measure_transmission_spectrum(setting['abs_average'], setting['abs_exposure'], filter_size = setting['filter_size'], dark_correction=True, do_plot=False)
    

        self.send_sample_to_cell(cell = 'absorption', draw_velocity=setting['abs_draw_velocity'], dispense_velocity=setting['abs_dispense_velocity'])

        #need sometime until the solution reaches equiliblium (bubble??)
        print('waiting %s s for equibliration' %setting['abs_equibliration_time'])
        time.sleep(setting['abs_equibliration_time']) 

        #measure absorption spectrum
        self.log('Measure absorption dark {timestamp}')
        self.AP.measure_dark_spectrum(setting['dark_average'], setting['abs_exposure'], filter_size=setting['filter_size'],  do_plot=False)
        self.log('Measure absorption spectrum  {timestamp}')
        absorption['sample'], absorption['transmittance'], absorption['absorbance'] = self.AP.measure_absorption_spectrum(setting['abs_average'], setting['abs_exposure'], \
                                            absorption['reference'], filter_size=setting['filter_size'], dark_correction=True, do_plot=setting['abs_do_plot'])

        absorption['max'], absorption['lambda_max'] = self.AP.find_max(absorption['absorbance'], analysis_range=setting['abs_calc_range']) 
        absorption['end_index'], absorption['end_wavelength'] = self.AP.find_abs_end(absorption['absorbance'], setting['absorption_threshold'], analysis_range=setting['abs_calc_range'])     
        print('abs_max :  {:.4f} ({:.1f} nm)'.format(absorption['max'], absorption['lambda_max']))
        if absorption['end_wavelength']:
            print('abs_end :  {:.1f} nm'.format(absorption['end_wavelength']))

        #input('pause')
        self.collect_sample_from_cell(cell = 'absorption', draw_velocity=setting['abs_draw_velocity'], dispense_velocity=setting['abs_dispense_velocity'])

        return absorption
    

        ## start pl and abs measurement with pump
    def measure_TE(self, fname, setting, **kwargs):

        self.send_sample_to_cell(cell = 'TE', draw_velocity=setting['TE_draw_velocity'], dispense_velocity=setting['TE_dispense_velocity'])

        self.log('Measure transient emission {timestamp}')
        #TE.measure_TE(**kwargs)

        result = self.TE.measure_TE(save_filename = fname, fit_order = 1, fit_weight = 0.7, do_plot = False, **kwargs)

        self.collect_sample_from_cell(cell = 'TE', draw_velocity=setting['TE_draw_velocity'], dispense_velocity=setting['TE_dispense_velocity'])
        #self.pump.draw_and_dispense('flow_cell', 'vial', 1*ml, velocity=1000)

        return result


    def _check_instruments(self, measurements):
        flg = True
        if 'absorption' in measurements and self.AP == None:
            print('absorption setup is not active.')
            flg = False    
        elif 'PL' in measurements and self.AP == None:
            print('PL setup is not active.')
            flg = False
        elif 'TE' in measurements and self.TE == None:
            print('TE setup is not active.')
            flg = False
        return flg




    #TODO keep sample after the measurements
    def do_measurements(self, fname, measurements, sample_position, sample_volume, dilution, water_ratio, job = None, sample_info = None, **kwargs):

        if  self._check_instruments(measurements) == False:
            raise Exception()

        self.log('measurement start {timestamp}')

        results, uv, PL, absorption, TE = {}, None, None, None, None
        
        config, setting = self._load_setting(**kwargs)

        # calculation to send to flow_cell
        total_volume = dilution*sample_volume

        dilution_actual = total_volume/sample_volume
        print('dilution : {:.2f}'.format(dilution_actual))

        self.fill_reference(water_ratio, measurements) #TODO consider dilution on water ratio

        self.collect_sample_from_valve(sample_volume, sample_position, setting)
        if dilution > 1:
            self.sample_dilution(sample_volume, dilution_actual, setting)

        time.sleep(1)

        #do measurements
        if 'absorption' in measurements:
            absorption = self.measure_absorption(setting)

        #TODO dilution for PL

        if 'PL' in measurements:
            uv, PL = self.measure_PL(setting)
            
        if 'TE' in measurements:
            try:
                # TE = self.measure_TE(fname, setting, **kwargs)
                TE = self.measure_TE(fname, setting, **config['TE'])
                os.remove('%s_TE.pkl' %fname)
                del(TE['metadata']['sample'])
                config['TE'].update(copy.deepcopy(TE['metadata']))
                del(TE['metadata'])
            except:
                print('TE measurement failed')
                self.TE.laser_off()
            
        if absorption is not None and PL is not None:
            if absorption['end_index'] and 'gain_spectrum' in PL.keys():
                PL['max_gain_factor'], PL['max_gain_wavelength'] = self._find_maximum_gain(PL['gain_spectrum'], absorption['end_index'], calc_range = setting['PL_calc_range'])

        results = {'uv' : uv,  'absorption' : absorption, 'PL' :  PL,  'TE' : TE, 'metadata' : config}

        if job:
            results['job'] = job

        if sample_info:
            results['metadata']['sample'] = sample_info

        if fname:
            self.AP.save_pkl(fname + '.pkl', results)
            self.write_result_csv(fname + '_AbsPL.csv', results)
            self.abspl_result_plots(fname, results)
            self.join_images(fname, glob.glob('%s*.png' %fname))
        self.log('discard sample {timestamp}')
        self.pump.draw_and_dispense('vial', 'waste', 1*ml, velocity=2000)

        #wash flow cells and vial
        for i, cell in enumerate(measurements):
            if i == 0:
                n = 3
            else: n = 2
            self.cell_wash([flow_cells[cell]['name']], 0.5*ml, n)

        self.vial_wash(1.5*total_volume, 3)

        self.collector_wash(0.3*ml, 3, sample_position)
        # self.collector_wash(2*sample_volume, 3, sample_position)

        self.log('measurement done {timestamp}')

        return results


    #for auto measurements############################
    def load_file_content(self, file_name):
        with open(file_name, 'rb') as content:
            return pickle.load(content)


    def experiment_params(self, file_content, minimum_volume, maximum_abs):

        save_dir = 'C:/Users/MatterLab/Dropbox/PythonScript/HPLCMS_characterization/sample_measured/%s' %today_formatted
        # save_dir = save_filepath +'%s_%s_vial%s' %(file_content['injection_name'], file_content['target_name'], file_content['vial_number'])
        if os.path.exists(save_dir) == False:
            os.mkdir(save_dir)
        file_content['filename'] = save_dir + '/%s_%s_vial%s' %(file_content['injection_name'], file_content['target_name'], file_content['vial_number'])
        file_content['dilution'] = max(1, file_content['average_absorbance_375']/maximum_abs/1000, minimum_volume/file_content['sample_volume'])
        # params = { 
        #         'filename' : save_dir + '/%s_%s_vial%s' %(file_content['injection_name'], file_content['target_name'], file_content['vial_number']),
        #         'dilution' :  max(1, file_content['average_absorbance_375']/maximum_abs/1000, minimum_volume/file_content['sample_volume']),
        #         }
        return file_content
        

    def auto_measurement(self, measurements = ['absorption','PL', 'TE'], minimum_volume = 0.15, maximum_abs = 1, measure_blank = False):

        def blank_measurement():

            today = datetime.date.today()
            today_formatted = today.strftime("%Y%m%d")
            save_dir = 'C:/Users/MatterLab/Dropbox/PythonScript/HPLCMS_characterization/sample_measured/%s' %today_formatted
            if os.path.exists(save_dir) == False:
                os.mkdir(save_dir)

            print('measuring blank')
            fname = '%s/blank' %save_dir
            self.measure_blank(fname, measurements = measurements, sample_position = 2, sample_volume = 0.2*ml, \
                                            sample_info ={'name' : 'Blank', 'concentration(uM)' : 0, 'solvent' : 'ACN'}) 
            print('blank measurement done')

        input_folder = self.config['data_path']['job_input']

        if measure_blank:
            blank_measurement()

        while True:
            file_names = glob.glob(input_folder + '/*pkl')
            print('# --> file_names', file_names)
            for file_name in file_names:
                print(os.path.basename(file_name))
                if os.path.basename(file_name) == 'blank.pkl':
                    if 'TE' in measurements:
                        self.TE.detector_on()
                    blank_measurement()
                elif os.path.basename(file_name) == 'shutdown.pkl':
                    self.close()
                else:
                    # load parameter file
                    file_content = self.load_file_content(file_name)
                    file_content = self.experiment_params(file_content, minimum_volume= minimum_volume, maximum_abs = maximum_abs)
                    print(file_content)
                    # collect measurements for submitted parameters
                    self.do_measurements(file_content['filename'], measurements = measurements, sample_position = file_content['vial_number'], \
                        sample_volume = file_content['sample_volume'] *ml, dilution = file_content['dilution'], water_ratio = 0, job = file_content) 
                # remove parameter file
                os.remove(file_name)
                time.sleep(5)
            time.sleep(5)

    def measure_blank(self, fname, measurements, sample_position, sample_volume = 0.2*ml, **kwargs):

        self.selector = Valco_valve('visa://10.22.1.20/ASRL17::INSTR', dev_id = 0, mode = 3, position = 1)
        self.valve = Valco_valve('visa://10.22.1.20/ASRL4::INSTR', dev_id = 0, mode = 1, position = 'A')
        self.selector.move_to(sample_position)
        self.draw_and_dispense('ACN', 'valve', sample_volume, draw_velocity=500, dispense_velocity=500)
        time.sleep(5)

        self.do_measurements(fname, measurements = measurements, sample_position = sample_position, sample_volume = sample_volume, dilution = 1, water_ratio = 0, **kwargs) 


if __name__ == '__main__':


    #initialize the device############
    Opt = Optical_measurements(TE = True, AbsPL = True)
    ##############

    ####Automeasurement###########
    Opt.auto_measurement(measurements = ['absorption','PL','TE'], minimum_volume = 0.13, maximum_abs = 1, measure_blank=False)

    #fill cells########
    #Opt.pump.draw(volume = 1*ml, valve='valve')
    #time.sleep(10)
    #Opt.pump.dispense(volume = 1*ml, valve='vial')
    #Opt.draw_and_dispense('ACN', 'waste', 1*ml, draw_velocity=500, dispense_velocity=500)
    #Opt.draw_and_dispense('ACN', 'waste', 1*ml, draw_velocity=500, dispense_velocity=500)
    #Opt.draw_and_dispense('ACN', 'waste', 1*ml, draw_velocity=500, dispense_velocity=500)
    #Opt.draw_and_dispense('ACN', 'flow_cell', 0.5*ml, draw_velocity=500, dispense_velocity=500)
    #Opt.draw_and_dispense('air', 'valve', 1*ml, draw_velocity=2000, dispense_velocity=2000)
    # Opt.draw_and_dispense('air', 'valve', 1*ml, draw_velocity=1000, dispense_velocity=1000)
    
    #####initialize#####
    #Opt.draw_and_dispense('ACN', 'flow_cell_PL', 0.5*ml, draw_velocity=500, dispense_velocity=500)
    #Opt.draw_and_dispense('ACN', 'flow_cell_PL', 0.5*ml, draw_velocity=500, dispense_velocity=500)
    #Opt.draw_and_dispense('ACN', 'flow_cell_abs', 0.5*ml, draw_velocity=500, dispense_velocity=500)
    #Opt.draw_and_dispense('ACN', 'flow_cell', 0.5*ml, draw_velocity=500, dispense_velocity=500)
    #Opt.vial_wash(0.3*ml, 2)
    # # # Opt.selector = Valco_valve('visa://10.22.1.20/ASRL17::INSTR', dev_id = 0, mode = 3, position = 1)
    # # # Opt.valve = Valco_valve('visa://10.22.1.20/ASRL4::INSTR', dev_id = 0, mode = 1, position = 'A')
    # # # # Opt.selector.move_to(2)
    # # # # Opt.draw_and_dispense('ACN', 'valve', 0.2*ml, draw_velocity=500, dispense_velocity=500)
    #Opt.collector_wash(0.3*ml, 3, 2)
    # # Opt.collector_wash(0.2*ml, 3, 3)
    #Opt.collector_wash(0.2*ml, 3, 9)
    ############

    #fill vial#################
    # Opt.selector = Valco_valve('visa://10.22.1.20/ASRL17::INSTR', dev_id = 0, mode = 3, position = 1)
    # Opt.valve = Valco_valve('visa://10.22.1.20/ASRL4::INSTR', dev_id = 0, mode = 1, position = 'A')
    # Opt.selector.move_to(3)
    # Opt.draw_and_dispense('ACN', 'valve', 0.2*ml, draw_velocity=500, dispense_velocity=500)
    # # Opt.selector.move_to(10)7
    # # Opt.draw_and_dispense('ACN', 'valve', 0.2*ml, draw_velocity=500, dispense_velocity=500)
    # Opt.selector.close_device()
    # Opt.valve.close_device()
    # time.sleep(10)

    #manual measurment_abs_PL_TE#############
    # import os 

    # sample_info ={
    #     'name' : 'Blank',
    #     # 'name' : 'Diphenylanthracene',
    #     'concentration(uM)' : 0,
    #     'solvent' : 'ACN'
    # }

    # path = 'C:/Users/MatterLab/Dropbox/PythonScript/kazu/data/20201105_blank'
    # if os.path.exists(path) == False:
    #    os.mkdir(path)
    # fname = '%s/%s_%s_in_%s_test2' %(path, sample_info['concentration(uM)'], sample_info['name'], sample_info['solvent'])
    # fname2 = '%s/%s_%s_in_%s_via3_1' %(path, sample_info['concentration(uM)'], sample_info['name'], sample_info['solvent'])
    # fname3 = '%s/%s_%s_in_%s_via4_1' %(path, sample_info['concentration(uM)'], sample_info['name'], sample_info['solvent'])
    # fname4 = '%s/%s_%s_in_%s_via5_1' %(path, sample_info['concentration(uM)'], sample_info['name'], sample_info['solvent'])
    # fname5 = '%s/%s_%s_in_%s_via8_1' %(path, sample_info['concentration(uM)'], sample_info['name'], sample_info['solvent'])
    # fname6 = '%s/%s_%s_in_%s_via9_1' %(path, sample_info['concentration(uM)'], sample_info['name'], sample_info['solvent'])
    # fname7 = '%s/%s_%s_in_%s_via10_1' %(path, sample_info['concentration(uM)'], sample_info['name'], sample_info['solvent'])
    # #fname2 = '%s/%s_%s_in_%s_6' %(path, sample_info['concentration(uM)'], sample_info['name'], sample_info['solvent'])
    # #fname3 = '%s/%s_%s_in_%s_3' %(path, sample_info['concentration(uM)'], sample_info['name'], sample_info['solvent'])

    #Opt.do_measurements(fname, measurements = ['absorption', 'PL','TE'], sample_position = 2, sample_volume = 0.1*ml, dilution = 2, water_ratio = 0, sample_info=sample_info) 
    # # Opt.do_measurements(fname2, measurements = ['absorption'], sample_position = 10, sample_volume = 0.1*ml, dilution = 1, water_ratio = 0, sample_info=sample_info) 
    # #Opt.do_measurements(fname2, measurements = ['absorption', 'PL','TE'], sample_position = 3, sample_volume = 0.1*ml, dilution = 1, water_ratio = 0, sample_info=sample_info)
    # #Opt.do_measurements(fname3, measurements = ['absorption', 'PL','TE'], sample_position = 9, sample_volume = 0.1*ml, dilution = 1, water_ratio = 0, sample_info=sample_info)
    # #Opt.do_measurements(fname, measurements = ['absorption'], sample_position = 2, sample_volume = 0.1*ml, dilution = 1, water_ratio = 0, sample_info=sample_info)
    # #Opt.do_measurements(fname, measurements = ['TE'], dilution = 1, water_ratio = 0, sample_info=sample_info)
    
    #Opt.measure_blank(fname, measurements = ['absorption','PL','TE'], sample_position = 3, sample_volume = 0.2*ml, sample_info=sample_info) 
    #Opt.measure_blank(fname2, measurements = ['absorption', 'PL'], sample_position = 3, sample_volume = 0.2*ml, sample_info=sample_info) 
    # Opt.measure_blank(fname3, measurements = ['absorption', 'PL'], sample_position = 4, sample_volume = 0.2*ml, sample_info=sample_info) 
    # Opt.measure_blank(fname4, measurements = ['absorption', 'PL'], sample_position = 5, sample_volume = 0.2*ml, sample_info=sample_info) 
    # Opt.measure_blank(fname5, measurements = ['absorption', 'PL'], sample_position = 8, sample_volume = 0.2*ml, sample_info=sample_info) 
    # Opt.measure_blank(fname6, measurements = ['absorption', 'PL'], sample_position = 9, sample_volume = 0.2*ml, sample_info=sample_info) 
    # Opt.measure_blank(fname7, measurements = ['absorption', 'PL'], sample_position = 10, sample_volume = 0.2*ml, sample_info=sample_info) 
    ############

    #Opt.measure_PL_manual(fname, sample_info=sample_info) 



    ###shut down########
    #Opt.close()

    ###measure line#############
    #Opt = Optical_measurements(TE=False, AbsPL=True)

    #Opt.mgr.pump.draw_and_dispense('air', 'flow_cell_PL', 1*ml, velocity=1000)
    #Opt.mgr.pump.draw_and_dispense('flow_cell_PL', 'waste', 1*ml, velocity=1000)
    #Opt.measure_line('flow_cell_PL', fill='valve')
    #Opt.mgr.pump.draw_and_dispense('valve', 'flow_cell_PL', 0.34*ml, velocity=1000)
    #input()
    #Opt.mgr.pump.draw_and_dispense('valve', 'flow_cell_PL', 0.39*ml, velocity=1000)

    # Opt.pump.draw_and_dispense('valve', 'waste', 1*ml, velocity=1000)
    # Opt.pump.draw_and_dispense('ACN', 'waste', 0.1*ml, velocity=1000)
    # Opt.measure_line('valve', fill='ACN', volume=0.1*ml, step=0.005*ml)

    ###########################

    ###washing##############

    # for _ in range(4):
    #     mgr.pump.draw_and_dispense('valve', 'flow_cell_PL', to_cell_over_PL, velocity=500)
    # log('Wash Absorption flow cell')
    # for _ in range(4):
    #     mgr.pump.draw_and_dispense('valve', 'flow_cell', to_cell_over, velocity=500)


    ###washing###############

    #mgr.pump.draw_and_dispense('flow_cell_PL', 'waste', 1*ml, velocity=2000)
    #mgr.pump.draw_and_dispense('ACN', 'flow_cell_PL', 2*ml, velocity=1000)

    #mgr.pump.draw(volume = 0.5*ml, valve='ACN')
    #mgr.pump.set_velocity(100)
    #mgr.pump.dispense_all(valve='flow_cell_PL')
    ##############


    ###test new PL#############
    # results = Opt.AP.measure_PL_spectrum2(30,  0.3,  led_power = 10,\
    #                                 filter_size = 20, dark_correction = False, spectral_correction = True, do_plot = False)
    # print(results['uv_average'], results['uv_start'], results['uv_end'], results['duration'], results['average'] )
    # plt.plot(results['PL']['wavelength'], results['PL_spectrum'][1])
    # plt.show()
    ##############

    #print(Opt.check_valve_status())





