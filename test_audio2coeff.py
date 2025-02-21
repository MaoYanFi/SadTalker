import os 
import torch
import numpy as np
from scipy.io import savemat
from yacs.config import CfgNode as CN
from scipy.signal import savgol_filter

from audio2pose_models.audio2pose import Audio2Pose
from audio2exp_models.networks import SimpleWrapperV2 
from audio2exp_models.audio2exp import Audio2Exp  

def load_cpk(checkpoint_path, model=None, optimizer=None, device="cpu"):
    checkpoint = torch.load(checkpoint_path, map_location=torch.device(device))
    if model is not None:
        model.load_state_dict(checkpoint['model'])
    if optimizer is not None:
        optimizer.load_state_dict(checkpoint['optimizer'])

    return checkpoint['epoch']

class Audio2Coeff():

    def __init__(self, audio2pose_checkpoint, audio2pose_yaml_path, 
                        audio2exp_checkpoint, audio2exp_yaml_path, 
                        wav2lip_checkpoint, device):
        #load config
        fcfg_pose = open(audio2pose_yaml_path)
        cfg_pose = CN.load_cfg(fcfg_pose)
        cfg_pose.freeze()
        fcfg_exp = open(audio2exp_yaml_path)
        cfg_exp = CN.load_cfg(fcfg_exp)
        cfg_exp.freeze()

        # load audio2pose_model
        self.audio2pose_model = Audio2Pose(cfg_pose, wav2lip_checkpoint, device=device)
        self.audio2pose_model = self.audio2pose_model.to(device)
        self.audio2pose_model.eval()
        for param in self.audio2pose_model.parameters():
            param.requires_grad = False 
        try:
            load_cpk(audio2pose_checkpoint, model=self.audio2pose_model, device=device)
        except:
            raise Exception("Failed in loading audio2pose_checkpoint")

        # load audio2exp_model
        netG = SimpleWrapperV2()
        netG = netG.to(device)
        for param in netG.parameters():
            netG.requires_grad = False
        netG.eval()
        try:
            load_cpk(audio2exp_checkpoint, model=netG, device=device)
        except:
            raise Exception("Failed in loading audio2exp_checkpoint")
        self.audio2exp_model = Audio2Exp(netG, cfg_exp, device=device, prepare_training_loss=False)
        self.audio2exp_model = self.audio2exp_model.to(device)
        for param in self.audio2exp_model.parameters():
            param.requires_grad = False
        self.audio2exp_model.eval()
 
        self.device = device

    def generate(self, batch, coeff_save_dir, pose_style):

        with torch.no_grad():
            #test
            results_dict_exp= self.audio2exp_model.test(batch)
            exp_pred = results_dict_exp['exp_coeff_pred']                         #bs T 64

            #for class_id in  range(1):
            #class_id = 0#(i+10)%45
            #class_id = random.randint(0,46)                                   #46 styles can be selected 
            batch['class'] = torch.LongTensor([pose_style]).to(self.device)
            results_dict_pose = self.audio2pose_model.test(batch) 
            pose_pred = results_dict_pose['pose_pred']                        #bs T 6

            pose_pred = torch.Tensor(savgol_filter(np.array(pose_pred.cpu()), 13, 2, axis=1)).to(self.device)
            coeffs_pred = torch.cat((exp_pred, pose_pred), dim=-1)            #bs T 70

            coeffs_pred_numpy = coeffs_pred[0].clone().detach().cpu().numpy() 
        
            savemat(os.path.join(coeff_save_dir, '%s##%s.mat'%(batch['pic_name'], batch['audio_name'])),  
                    {'coeff_3dmm': coeffs_pred_numpy})
            torch.cuda.empty_cache()
            return os.path.join(coeff_save_dir, '%s##%s.mat'%(batch['pic_name'], batch['audio_name']))


