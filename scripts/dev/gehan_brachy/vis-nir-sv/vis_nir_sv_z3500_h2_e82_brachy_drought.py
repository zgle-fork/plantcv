#!/usr/bin/env python

import sys, traceback
import cv2
import os
import re
import numpy as np
import argparse
import string
import plantcv as pcv


def options():
    parser = argparse.ArgumentParser(description="Imaging processing with opencv")
    parser.add_argument("-i", "--image", help="Input image file.", required=True)
    parser.add_argument("-o", "--outdir", help="Output directory for image files.", required=False)
    parser.add_argument("-r","--result", help="result file.", required= False )
    parser.add_argument("-r2","--coresult", help="result file.", required= False )
    parser.add_argument("-D", "--debug", help="Turn on debug, prints intermediate images.", action="store_true")
    args = parser.parse_args()
    return args

### Main pipeline
def main():
  # Get options
  args = options()
  
  # Read image
  img, path, filename = pcv.readimage(args.image)
    
  # Pipeline step
  device = 0

  # Convert RGB to HSV and extract the Saturation channel
  device, s = pcv.rgb2gray_hsv(img, 's', device, args.debug)
  
  # Threshold the Saturation image
  device, s_thresh = pcv.binary_threshold(s, 36, 255, 'light', device, args.debug)
  
  # Median Filter
  device, s_mblur = pcv.median_blur(s_thresh, 0, device, args.debug)
  device, s_cnt = pcv.median_blur(s_thresh, 0, device, args.debug)
  
  # Fill small objects
  #device, s_fill = pcv.fill(s_mblur, s_cnt, 0, device, args.debug)
  
  # Convert RGB to LAB and extract the Blue channel
  device, b = pcv.rgb2gray_lab(img, 'b', device, args.debug)
  
  # Threshold the blue image
  device, b_thresh = pcv.binary_threshold(b, 137, 255, 'light', device, args.debug)
  device, b_cnt = pcv.binary_threshold(b, 137, 255, 'light', device, args.debug)
  
  # Fill small objects
  #device, b_fill = pcv.fill(b_thresh, b_cnt, 10, device, args.debug)
  
  # Join the thresholded saturation and blue-yellow images
  device, bs = pcv.logical_and(s_mblur, b_cnt, device, args.debug)
  
  # Apply Mask (for vis images, mask_color=white)
  device, masked = pcv.apply_mask(img, bs, 'white', device, args.debug)
  
  # Convert RGB to LAB and extract the Green-Magenta and Blue-Yellow channels
  device, masked_a = pcv.rgb2gray_lab(masked, 'a', device, args.debug)
  device, masked_b = pcv.rgb2gray_lab(masked, 'b', device, args.debug)
  
  # Threshold the green-magenta and blue images
  device, maskeda_thresh = pcv.binary_threshold(masked_a, 127, 255, 'dark', device, args.debug)
  device, maskedb_thresh = pcv.binary_threshold(masked_b, 128, 255, 'light', device, args.debug)
  
  # Join the thresholded saturation and blue-yellow images (OR)
  device, ab = pcv.logical_or(maskeda_thresh, maskedb_thresh, device, args.debug)
  device, ab_cnt = pcv.logical_or(maskeda_thresh, maskedb_thresh, device, args.debug)
  
  # Fill small noise
  device, ab_fill1 = pcv.fill(ab, ab_cnt, 2, device, args.debug)
  
  # Dilate to join small objects with larger ones
  device, ab_cnt1=pcv.dilate(ab_fill1, 3, 2, device, args.debug)
  device, ab_cnt2=pcv.dilate(ab_fill1, 3, 2, device, args.debug)
  
  # Fill dilated image mask
  device, ab_cnt3=pcv.fill(ab_cnt2,ab_cnt1,150,device,args.debug)
  device, masked2 = pcv.apply_mask(masked, ab_cnt3, 'white', device, args.debug)
  
  # Convert RGB to LAB and extract the Green-Magenta and Blue-Yellow channels
  device, masked2_a = pcv.rgb2gray_lab(masked2, 'a', device, args.debug)
  device, masked2_b = pcv.rgb2gray_lab(masked2, 'b', device, args.debug)
  
  # Threshold the green-magenta and blue images
  device, masked2a_thresh = pcv.binary_threshold(masked2_a, 127, 255, 'dark', device, args.debug)
  device, masked2b_thresh = pcv.binary_threshold(masked2_b, 128, 255, 'light', device, args.debug)
  device, ab_fill = pcv.logical_or(masked2a_thresh, masked2b_thresh, device, args.debug)
  
  # Identify objects
  device, id_objects,obj_hierarchy = pcv.find_objects(masked2, ab_fill, device, args.debug)
  
  # Define ROI
  device, roi1, roi_hierarchy= pcv.define_roi(masked2,'rectangle', device, None, 'default', args.debug,True, 500, 0,-600,-885)
  
  # Decide which objects to keep
  device,roi_objects, hierarchy3, kept_mask, obj_area = pcv.roi_objects(img,'partial',roi1,roi_hierarchy,id_objects,obj_hierarchy,device, args.debug)
  
  # Object combine kept objects
  device, obj, mask = pcv.object_composition(img, roi_objects, hierarchy3, device, args.debug)
  
  ############## VIS Analysis ################  
  
  # Find shape properties, output shape image (optional)
  device, shape_header,shape_data,shape_img = pcv.analyze_object(img, args.image, obj, mask, device,args.debug,args.outdir+'/'+filename)
  
  # Shape properties relative to user boundary line (optional)
  device, boundary_header,boundary_data, boundary_img1= pcv.analyze_bound(img, args.image,obj, mask, 845, device,args.debug,args.outdir+'/'+filename)
  
  # Determine color properties: Histograms, Color Slices and Pseudocolored Images, output color analyzed images (optional)
  device, color_header,color_data,norm_slice= pcv.analyze_color(img, args.image, mask, 256, device, args.debug,'all','rgb','v','img',300,args.outdir+'/'+filename)
  
  # Output shape and color data

  result=open(args.result,"a")
  result.write('\t'.join(map(str,shape_header)))
  result.write("\n")
  result.write('\t'.join(map(str,shape_data)))
  result.write("\n")
  result.write('\t'.join(map(str,color_header)))
  result.write("\n")
  result.write('\t'.join(map(str,color_data)))
  result.write("\n")
  result.write('\t'.join(map(str,boundary_header)))
  result.write("\n")
  result.write('\t'.join(map(str,boundary_data)))
  result.write("\n")
    
############################# Use VIS image mask for NIR image#########################
  # Find matching NIR image
  device, nirpath=pcv.get_nir(path,filename,device,args.debug)
  nir, path1, filename1=pcv.readimage(nirpath)
  nir2=cv2.imread(nirpath,-1)
  
  # Flip mask
  device, f_mask= pcv.flip(mask,"vertical",device,args.debug)
  
  # Reize mask
  device, nmask = pcv.resize(f_mask, 0.1304,0.1304, device, args.debug)
  
  # position, and crop mask
  device,newmask=pcv.crop_position_mask(nir,nmask,device,65,3,"top","left",args.debug)
  
  # Identify objects
  device, nir_objects,nir_hierarchy = pcv.find_objects(nir, newmask, device, args.debug)
  
  # Object combine kept objects
  device, nir_combined, nir_combinedmask = pcv.object_composition(nir, nir_objects, nir_hierarchy, device, args.debug)

####################################### Analysis #############################################

  device, nhist_header, nhist_data, h_norm = pcv.analyze_NIR_intensity(nir2, filename1, newmask, 256, device, args.debug, args.outdir + '/' + filename1)
  device, nshape_header, nshape_data, ori_img = pcv.analyze_object(nir2, filename1, nir_combined, nir_combinedmask, device, args.debug, args.outdir + '/' + filename1)
  
  if args.debug:
    pcv.print_results(path1, nhist_header, nhist_data)
    pcv.print_results(path1, nshape_header, nshape_data)
  
  coresult=open(args.coresult,"a")
  coresult.write('\t'.join(map(str,nhist_header)))
  coresult.write("\n")
  coresult.write('\t'.join(map(str,nhist_data)))
  coresult.write("\n")
  coresult.write('\t'.join(map(str,nshape_header)))
  coresult.write("\n")
  coresult.write('\t'.join(map(str,nshape_data)))
  coresult.write("\n")

    
if __name__ == '__main__':
    main()