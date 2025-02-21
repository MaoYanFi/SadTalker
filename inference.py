import torch
from time import  strftime
import os, sys, time
from argparse import ArgumentParser

from utils.preprocess import CropAndExtract
from test_audio2coeff import Audio2Coeff  
from facerender.animate import AnimateFromCoeff
from generate_batch import get_data
from generate_facerender_batch import get_facerender_data

def main(args):
    #torch.backends.cudnn.enabled = False

    pic_path = args.source_image
    audio_path = args.driven_audio
    save_dir = os.path.join(args.result_dir, strftime("%Y_%m_%d_%H.%M.%S"))
    os.makedirs(save_dir, exist_ok=True)
    pose_style = args.pose_style
    device = args.device
    batch_size = args.batch_size
    camera_yaw_list = args.camera_yaw
    camera_pitch_list = args.camera_pitch
    camera_roll_list = args.camera_roll

    current_code_path = sys.argv[0]
    current_root_path = os.path.split(current_code_path)[0]

    os.environ['TORCH_HOME']=os.path.join(current_root_path, args.checkpoint_dir)

    path_of_lm_croper = os.path.join(current_root_path, args.checkpoint_dir, 'shape_predictor_68_face_landmarks.dat')
    path_of_net_recon_model = os.path.join(current_root_path, args.checkpoint_dir, 'epoch_20.pth')
    dir_of_BFM_fitting = os.path.join(current_root_path, args.checkpoint_dir, 'BFM_Fitting')
    wav2lip_checkpoint = os.path.join(current_root_path, args.checkpoint_dir, 'wav2lip.pth')

    audio2pose_checkpoint = os.path.join(current_root_path, args.checkpoint_dir, 'auido2pose_00140-model.pth')
    audio2pose_yaml_path = os.path.join(current_root_path, 'config', 'auido2pose.yaml')
    
    audio2exp_checkpoint = os.path.join(current_root_path, args.checkpoint_dir, 'auido2exp_00300-model.pth')
    audio2exp_yaml_path = os.path.join(current_root_path, 'config', 'auido2exp.yaml')

    free_view_checkpoint = os.path.join(current_root_path, args.checkpoint_dir, 'facevid2vid_00189-model.pth.tar')
    mapping_checkpoint = os.path.join(current_root_path, args.checkpoint_dir, 'mapping_00229-model.pth.tar')
    facerender_yaml_path = os.path.join(current_root_path, 'config', 'facerender.yaml')

    #init model
    print(path_of_net_recon_model)
    preprocess_model = CropAndExtract(path_of_lm_croper, path_of_net_recon_model, dir_of_BFM_fitting, device)

    print(audio2pose_checkpoint)
    print(audio2exp_checkpoint)
    audio_to_coeff = Audio2Coeff(audio2pose_checkpoint, audio2pose_yaml_path, 
                                audio2exp_checkpoint, audio2exp_yaml_path, 
                                wav2lip_checkpoint, device)
    
    print(free_view_checkpoint)
    print(mapping_checkpoint)
    animate_from_coeff = AnimateFromCoeff(free_view_checkpoint, mapping_checkpoint, 
                                            facerender_yaml_path, device)

    #crop image and extract 3dmm from image
    first_frame_dir = os.path.join(save_dir, 'first_frame_dir')
    os.makedirs(first_frame_dir, exist_ok=True)
    first_coeff_path, crop_pic_path =  preprocess_model.generate(pic_path, first_frame_dir)
    if first_coeff_path is None:
        print("Can't get the coeffs of the input")
        return

    #audio2ceoff
    batch = get_data(first_coeff_path, audio_path, device)
    coeff_path = audio_to_coeff.generate(batch, save_dir, pose_style)
    
    #coeff2video
    data = get_facerender_data(coeff_path, crop_pic_path, first_coeff_path, audio_path, 
                                batch_size, camera_yaw_list, camera_pitch_list, camera_roll_list,
                                expression_scale=args.expression_scale)
    
    animate_from_coeff.generate(data, save_dir,  enhancer=args.enhancer)
    video_name = data['video_name']

    if args.enhancer is not None:
        print(f'The generated video is named {video_name}_enhanced in {save_dir}')
    else:
        print(f'The generated video is named {video_name} in {save_dir}')

    
if __name__ == '__main__':

    parser = ArgumentParser()  
    parser.add_argument("--driven_audio", default='./examples/driven_audio/japanese.wav', help="path to driven audio")
    parser.add_argument("--source_image", default='./examples/source_image/art_0.png', help="path to source image")
    parser.add_argument("--checkpoint_dir", default='./checkpoints', help="path to output")
    parser.add_argument("--result_dir", default='./examples/results', help="path to output")
    parser.add_argument("--pose_style", type=int, default=0,  help="input pose style from [0, 46)")
    parser.add_argument("--batch_size", type=int, default=2,  help="the batch size of facerender")
    parser.add_argument("--expression_scale", type=int, default=1.,  help="the batch size of facerender")
    parser.add_argument('--camera_yaw', nargs='+', type=int, default=[0], help="the camera yaw degree")
    parser.add_argument('--camera_pitch', nargs='+', type=int, default=[0], help="the camera pitch degree")
    parser.add_argument('--camera_roll', nargs='+', type=int, default=[0], help="the camera roll degree")
    parser.add_argument('--enhancer',  type=str, default=None, help="Face enhancer, [GFPGAN]")
    parser.add_argument("--cpu", dest="cpu", action="store_true") 
    
    args = parser.parse_args()
    if torch.cuda.is_available() and not args.cpu:
        args.device = "cuda"
    else:
        args.device = "cpu"

    main(args)

