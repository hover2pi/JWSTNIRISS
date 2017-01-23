from astropy.io import fits #astropy modules for FITS IO
import numpy as np #numpy gives us better array management 
from scipy import interpolate #spline interpolation
from scipy.signal import convolve2d

def readresponse():
    "Usage: ld,res1,res2,res3=readresponse()"
    response_file="specgen/NIRISS_Throughput_EBOI.fits"
    hdulist = fits.open(response_file)
    tbdata = hdulist[1].data             #fetch table data for HUD=1
    reponse_ld=tbdata.field(0)[0]*10.0   #Wavelength (A) 
    reponse_n1=tbdata.field(22)[0]       #n=1 response
    reponse_n2=tbdata.field(23)[0]       #n=2 response
    reponse_n3=tbdata.field(24)[0]       #n=3 response
    return reponse_ld,reponse_n1,reponse_n2,reponse_n3;

def readstarmodel(starmodel_file,smodeltype):
    "Usage: starmodel_wv,starmodel_flux=readstarmodel(starmodel_file,smodeltype)"
    starmodel_wv=[]
    starmodel_flux=[]
    f = open(starmodel_file,'r')
    for line in f:
        line = line.strip() #get rid of \n at the end of the line
        columns = line.split() #break into columns with space delimiter
        starmodel_wv.append(float(columns[0])*10)
        flux=-float(columns[5])*np.pi*(42.0*float(columns[1])+70.0*float(columns[2])\
        	+90.0*float(columns[3])+105.0*float(columns[4])-210.0)/210.0
        starmodel_flux.append(np.max([0.0,flux]))
    f.close()
    
    starmodel_wv=np.array(starmodel_wv)
    starmodel_flux=np.array(starmodel_flux)
    return starmodel_wv,starmodel_flux;

def readplanetmodel(planetmodel_file,pmodeltype):
    "Usage: planetmodel_wv,planetmodel_depth=readplanetmodel(planetmodel_file,pmodeltype)"
    planetmodel_wv=[]
    planetmodel_depth=[]
    f = open(planetmodel_file,'r')
    for line in f:
        line = line.strip() #get rid of \n at the end of the line
        columns = line.split(',') #break into columns with comma
        if is_number(columns[0]): #ignore lines that start with '#' 
            planetmodel_wv.append(float(columns[0])*10000.0) #wavelength (A)   
            planetmodel_depth.append(float(columns[1]))      #transit deth (ppm)
    f.close()

    planetmodel_wv=np.array(planetmodel_wv)       #convert to numpy array
    planetmodel_depth=np.array(planetmodel_depth)
    
    return planetmodel_wv,planetmodel_depth;

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

def p2w(p,noversample,ntrace):
    "Usage: w=p2w(p,noversample,ntrace) Converts x-pixel (p) to wavelength (w)"
    
    #co-efficients for polynomial that define the trace-position
    nc=5 #number of co-efficients
    c=[[2.60188,-0.000984839,3.09333e-08,-4.19166e-11,1.66371e-14],\
     [1.30816,-0.000480837,-5.21539e-09,8.11258e-12,5.77072e-16],\
     [0.880545,-0.000311876,8.17443e-11,0.0,0.0]]
    
    pix=p/noversample
    w=c[ntrace-1][0]
    for i in range(1,nc):
        #print(w)
        w+=np.power(pix,i)*c[ntrace-1][i]
    w*=10000.0 #um to A
                  
    return w

def w2p(w,noversample,ntrace):
    "Usage: p=w2p(p,noversample,ntrace) Converts wavelength (w) to x-pixel (p)"
    nc=5
    
    c=[[2957.38,-1678.19,526.903,-183.545,23.4633],\
       [3040.35,-2891.28,682.155,-189.996,0.0],\
       [2825.46,-3211.14,2.69446,0.0,0.0]]
    
    wum=w/10000.0 #A->um
    p=c[ntrace-1][0]
    for i in range(1,nc):
        #print(p)
        p+=np.power(wum,i)*c[ntrace-1][i]
    p=p*noversample
                  
    return p    

def addflux2pix(px,py,pixels,pixelnorm,fmod):
    "Drizel Flux onto Pixels using a square PSF of size unity"
    
    xmax=pixels.shape[0] #Size of pixel array
    ymax=pixels.shape[1]
    
    pxmh=px-0.5 #location of reference corner of PSF square
    pymh=py-0.5
    
    dx=np.floor(px+0.5)-pxmh
    dy=np.floor(py+0.5)-pymh
 
    npx=int(pxmh) #Numpy arrays start at zero
    npy=int(pymh) 
    if npx >= 0 and npx < xmax and npy >=0 and npy < ymax:
        pixels[npx,npy]+=fmod*dx*dy
        pixelnorm[npx,npy]+=1
        
    npx=int(pxmh)+1
    npy=int(pymh)
    if npx >= 0 and npx < xmax and npy >=0 and npy < ymax:
        pixels[npx,npy]+=fmod*(1.0-dx)*dy
        pixelnorm[npx,npy]+=1

    npx=int(pxmh)
    npy=int(pymh)+1
    if npx >= 0 and npx < xmax and npy >=0 and npy < ymax:
        pixels[npx,npy]+=fmod*dx*(1.0-dy)
        pixelnorm[npx,npy]+=1

    npx=int(pxmh)+1
    npy=int(pymh)+1
    if npx >= 0 and npx < xmax and npy >=0 and npy < ymax:
        pixels[npx,npy]+=fmod*(1.0-dx)*(1.0-dy)
        pixelnorm[npx,npy]+=1

    #print(pixels[npx,npy],npx,npy,px,py)
    #input()
    return pixels,pixelnorm;

def ptrace(px,noversample,ntrace):
    "given x-pixel, return y-position based on trace"
    nc=5 #number of co-efficients
    c=[[275.685,0.0587943,-0.000109117,1.06605e-7,-3.87e-11],\
      [254.109,-0.00121072,-1.84106e-05,4.81603e-09,-2.14646e-11],\
      [203.104,-0.0483124,-4.79001e-05,0.0,0.0]]
    
    opx=px/noversample #account for oversampling
    
    ptrace=c[ntrace-1][0]
    for i in range(1,nc):
        #print(w)
        ptrace+=np.power(opx,i)*c[ntrace-1][i]
        
    ptrace=ptrace-128
    return ptrace;

def genunconvolveimg(xout,yout,noversample,response_ld,response_n1,starmodel_wv,\
 starmodel_flux):
    "Generate Unconvolved 2D Image"
    pixels=np.zeros((xout*noversample,yout*noversample))
    pixelnorm=np.zeros((xout*noversample,yout*noversample))

    response_spl = interpolate.splrep(response_ld, response_n1, s=0)
    rmax=np.max(response_ld)
    rmin=np.min(response_ld)
    for k in range(starmodel_wv.shape[0]):
    
        w=starmodel_wv[k]
        i=w2p(w,noversample,1)
        j=ptrace(i,noversample,1)
        if w < rmax and w > rmin:
            response_one = interpolate.splev(w, response_spl, der=0)
        else:
            response_one = 0
        flux=starmodel_flux[k]*response_one
        pixels,pixelnorm=addflux2pix(i,j,pixels,pixelnorm,flux)
    
    #Normalized the drizzled pixels
    pixels=pixels/np.ma.array(pixelnorm,mask=(pixelnorm==0))

    return pixels;

def convolveimg(pixels):
    waverange=np.arange(500,3500,100) #central wavelength for each PSF model 
    nsubimg=len(waverange)            #number of PSF models
    ncol=len(pixels)                  #number of columns in 2D image
    columnmaps=np.zeros((nsubimg,ncol))    #map each column to sub-image for convolution
    ncolmap=np.zeros(nsubimg) #number of columns in each sub-image
    columnweights=np.zeros((nsubimg,ncol)) #weight of each column in sub-image
    for i in range(ncol):
        wav=p2w(i+1,1,1)/10  #convert pixel to wavelength 
        nwav=int((wav-500)/100) #identify appropriate PSF model 

        j=0
        if nwav+j >= 0 and nwav+j < nsubimg:
            ncolmap[nwav+j]+=1
            columnmaps[nwav+j,int(ncolmap[nwav+j]-1)]=i+1
            weight=1-np.abs(waverange[nwav+j]-wav)/100
            columnweights[nwav+j,int(ncolmap[nwav+j]-1)]=weight
    
        j=1
        if nwav+j >= 0 and nwav+j < nsubimg:
            ncolmap[nwav+j]+=1
            columnmaps[nwav+j,int(ncolmap[nwav+j]-1)]=i+1
            weight=1-np.abs(waverange[nwav+j]-wav)/100
            columnweights[nwav+j,int(ncolmap[nwav+j]-1)]=weight
    
        j=2
        if nwav+j >= 0 and nwav+j < nsubimg:
            ncolmap[nwav+j]+=1
            columnmaps[nwav+j,int(ncolmap[nwav+j]-1)]=i+1
            weight=1-np.abs(waverange[nwav+j]-wav)/100
            columnweights[nwav+j,int(ncolmap[nwav+j]-1)]=0
    
        j=1-1
        if nwav+j >= 0 and nwav+j < nsubimg:
            ncolmap[nwav+j]+=1
            columnmaps[nwav+j,int(ncolmap[nwav+j]-1)]=i+1
            weight=1-np.abs(waverange[nwav+j]-wav)/100
            columnweights[nwav+j,int(ncolmap[nwav+j]-1)]=0


    cimage=np.zeros(pixels.shape)
    for i in range(nsubimg):
        if ncolmap[i]>0 :
            subimg=np.zeros((int(ncolmap[i]),pixels.shape[1]))
            for j in range(int(ncolmap[i])):
                subimg[j,:]=pixels[int(columnmaps[i,j]-1),:]
            kfile="specgen/Kernels1/psf_"+str(int(waverange[i]))+"nm_x10_oversampled.fits"
            hdulist = fits.open(kfile) #open the FITS file
            psfdata = hdulist[0].data #extract the Image
            csubimg=convolve2d(subimg,psfdata,mode='same')
        
            for j in range(int(ncolmap[i])):
                cimage[int(columnmaps[i,j]-1),:]+=csubimg[j,:]*columnweights[i,j]

    return cimage;
