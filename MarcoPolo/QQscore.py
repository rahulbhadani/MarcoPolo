#!/usr/bin/env python
# coding: utf-8

# In[3]:


import sys
import multiprocessing
import pickle

import numpy as np
import pandas as pd
from scipy.io import mmread

import torch
import torch.optim as optim
from torch.utils.data import DataLoader

from MarcoPolo.models import MarcoPolo_Model
from MarcoPolo.trainer import run_EM_trick

from MarcoPolo.dataloader import Cell_Dataset


# In[2]:


def get_QQscore(Y, X, s, num_cluster_list, LR, EM_ITER_MAX, M_ITER_MAX, LL_diff_tolerance, Q_diff_tolerance, device, verbose=False):
    print('num_cluster_list',num_cluster_list)
    print('Y: {} X: {} s: {}'.format(Y.shape,X.shape,s.shape))
    
    device=torch.device(device)
    
    gamma_list_list=[]
    
    Q_list_list=[]
    LL_list_list=[]
    em_idx_max_list_list=[]
    m_idx_max_list_list=[]
    
    delta_log_list_list=[]
    beta_list_list=[]
    #Y_device=torch.Tensor(Y).to(device)
    
    
    
    for num_cluster in num_cluster_list:
        print('\nTesting num_cluster={}'.format(num_cluster))

        gamma_list=[]
        
        Q_list=[]
        LL_list=[]
        em_idx_max_list=[]
        m_idx_max_list=[]
        
        delta_log_list=[]
        beta_list=[]        
        
        for iter_idx,exp_data_idx in enumerate(np.arange(Y.shape[1])):
            if iter_idx%10==0:
                sys.stdout.write('\rComplete number of Gene: {}'.format(iter_idx))        
                sys.stdout.flush()
            cell_dataset=Cell_Dataset(Y[:,iter_idx:iter_idx+1],X,s)
            
            cell_dataloader=DataLoader(dataset=cell_dataset,shuffle=False,batch_size=Y.shape[0],num_workers=0)        

            if iter_idx==0:
                model=MarcoPolo_Model(Y=Y[:,iter_idx:iter_idx+1],rho=np.ones((num_cluster,1)),X_col=X.shape[1],delta_min=0).to(device)
            else:
                model.init_parameter_delta_min(0)
                model.init_paramter_Y(Y[:,iter_idx:iter_idx+1])                
            optimizer = optim.Adamax(model.parameters(),lr=LR)#,betas=(0.92, 0.999))
            gamma_new, Q_new, LL_new, em_idx_max, m_idx_max=run_EM_trick(model=model,optimizer=optimizer,cell_dataloader=cell_dataloader, device=device, EM_ITER_MAX=EM_ITER_MAX, M_ITER_MAX=M_ITER_MAX, LL_diff_tolerance=LL_diff_tolerance,Q_diff_tolerance=Q_diff_tolerance,verbose=verbose)
            
            gamma_list.append(gamma_new.cpu().numpy())
            
            Q_list.append(Q_new.detach().cpu().numpy())
            LL_list.append(LL_new.detach().cpu().numpy())
            em_idx_max_list.append(em_idx_max)
            m_idx_max_list.append(m_idx_max)
            
            delta_log_list.append(model.delta_log.detach().cpu().numpy())
            beta_list.append(model.beta.detach().cpu().numpy())            
            
            
        gamma_list_list.append(gamma_list)
        
        Q_list_list.append(Q_list)        
        LL_list_list.append(LL_list)
        em_idx_max_list_list.append(em_idx_max_list)
        m_idx_max_list_list.append(m_idx_max_list)
        
        delta_log_list_list.append(delta_log_list)
        beta_list_list.append(beta_list)
        
    
    result_list=[pd.DataFrame([Q_list_list[num_cluster_list_idx],
                                LL_list_list[num_cluster_list_idx],
                                em_idx_max_list_list[num_cluster_list_idx],
                                m_idx_max_list_list[num_cluster_list_idx]],index=['Q','LL','em_idx_max','m_idx_max']).T
                 for num_cluster_list_idx,num_cluster in enumerate(num_cluster_list)]

    
    #num_cluster_list_idx
    #[Q_list_list,LL_list_list,em_idx_max_list_list,m_idx_max_list_list]
    #result=pd.DataFrame([Q_list_list,LL_list_list,em_idx_max_list_list,m_idx_max_list_list],index=num_cluster_list).T
    
    return gamma_list_list,result_list,delta_log_list_list,beta_list_list


# In[8]:


def save_QQscore(path='datasets/extract/{}', Covar=None, num_cluster_list=[1,2], LR=0.1, EM_ITER_MAX=20, M_ITER_MAX=10000,LL_diff_tolerance=1e-4, Q_diff_tolerance=1e-4, device='cuda:{}'.format(0),verbose=False):    
    """
    Save QQ
    :param path str: input/output path
    :param Covar numpy.array: covariate
    """        
    exp_data=mmread('{}.data.counts.mm'.format(path)).toarray().astype(float)
    with open('{}.data.col'.format(path),'r') as f: exp_data_col=[i.strip().strip('"') for i in f.read().split()]
    with open('{}.data.row'.format(path),'r') as f: exp_data_row=[i.strip().strip('"') for i in f.read().split()]
    assert exp_data.shape==(len(exp_data_row),len(exp_data_col))
    assert len(set(exp_data_row))==len(exp_data_row)
    assert len(set(exp_data_col))==len(exp_data_col)  
    
    cell_size_factor=pd.read_csv('{}.size_factor.tsv'.format(path),sep='\t',header=None)[0].values.astype(float)#.reshape(-1,1)
    
    if Covar is None:
        x_data_intercept=np.array([np.ones(exp_data.shape[1])]).transpose()
        x_data_null=np.concatenate([x_data_intercept],axis=1)    
    else:
        x_data_null=Covar
        #print(x_data_null.shape)
        # cell count x covar dim (8444 x 1)
    

    QQscore_result=get_QQscore(Y=exp_data.transpose()[:,:], X=x_data_null[:], s=cell_size_factor[:], num_cluster_list=num_cluster_list, LR=LR, EM_ITER_MAX=EM_ITER_MAX, M_ITER_MAX=M_ITER_MAX, LL_diff_tolerance=LL_diff_tolerance, Q_diff_tolerance=Q_diff_tolerance, device=device, verbose=verbose)
    
    gamma_list_list,result_list,delta_log_list_list,beta_list_list=QQscore_result
    
    
    for num_cluster_list_idx,num_cluster in enumerate(num_cluster_list):
        result_list[num_cluster_list_idx].to_csv('{}.QQscore.{}.tsv'.format(path,num_cluster),sep='\t')
    
        with open('{}.QQscore.{}.gamma_list.pickle'.format(path,num_cluster), 'wb') as f:
            pickle.dump(gamma_list_list[num_cluster_list_idx], f)
        with open('{}.QQscore.{}.delta_log_list.pickle'.format(path,num_cluster), 'wb') as f:
            pickle.dump(delta_log_list_list[num_cluster_list_idx], f)
        with open('{}.QQscore.{}.beta_list.pickle'.format(path,num_cluster), 'wb') as f:
            pickle.dump(beta_list_list[num_cluster_list_idx], f)            


# In[ ]:


def read_QQscore(path,num_cluster_list=[1,2]):
    """
    read QQ
    :param path str: input/output path
    """        
    result_list=[]
    gamma_list_list=[]
    delta_log_list_list=[]
    beta_list_list=[]
    
    for num_cluster_list_idx,num_cluster in enumerate(num_cluster_list):
        result_list.append(pd.read_csv('{}.QQscore.{}.tsv'.format(path,num_cluster),sep='\t',index_col=0))
        with open('{}.QQscore.{}.gamma_list.pickle'.format(path,num_cluster), 'rb') as f:
            gamma_list_list.append(pickle.load(f))
        with open('{}.QQscore.{}.delta_log_list.pickle'.format(path,num_cluster), 'rb') as f:
            delta_log_list_list.append(pickle.load(f))
        with open('{}.QQscore.{}.beta_list.pickle'.format(path,num_cluster), 'rb') as f:
            beta_list_list.append(pickle.load(f))            
            
    return result_list,gamma_list_list,delta_log_list_list,beta_list_list


# In[ ]:


"""
def gamma_to_gamma_argmax(gamma):
    gamma_argmax=np.argmax(gamma,axis=1)
    gamma_argmax_counts=np.unique(gamma_argmax,return_counts=True)
    key_newkey=pd.DataFrame(gamma_argmax_counts,index=['idx','counts']).T.set_index('idx').sort_values(by='counts',ascending=True).index.tolist()
    gamma_argmax=[key_newkey.index(argmax) for argmax in gamma_argmax]

    return gamma_argmax
"""
"""
def gamma_exp_to_gamma_argmax(gamma,exp_data_select=None):
    gamma_argmax=np.argmax(gamma,axis=1)
    gamma_argmax_counts=list(np.unique(gamma_argmax,return_counts=True))
    if exp_data_select is None:
        key_newkey=pd.DataFrame(gamma_argmax_counts,index=['idx','counts']).T.set_index('idx').sort_values(by='counts',ascending=True).index.tolist()
    else:
        gamma_argmax_counts_lfc=gamma_argmax_counts+\
        [np.log10(list(map(lambda x: np.mean(exp_data_select[gamma_argmax==x],axis=0)/np.mean(exp_data_select[gamma_argmax!=x],axis=0), gamma_argmax_counts[0])))]
        key_newkey=pd.DataFrame(gamma_argmax_counts_lfc,index=['idx','counts','lfc']).T.astype({'idx':int,'counts':int}).set_index('idx').sort_values(by='lfc',ascending=False).index.tolist()
    gamma_argmax=[key_newkey.index(argmax) for argmax in gamma_argmax]

    return gamma_argmax
"""    

def gamma_exp_to_gamma_argmax(gamma,exp_data_select=None):
    gamma_argmax=np.argmax(gamma,axis=1)
    gamma_argmax_counts=list(np.unique(gamma_argmax,return_counts=True))
    if exp_data_select is None:
        key_newkey=pd.DataFrame(gamma_argmax_counts,index=['idx','counts']).T.set_index('idx').sort_values(by='counts',ascending=True).index.tolist()
    else:
        gamma_argmax_counts_lfc=gamma_argmax_counts+        [(list(map(lambda x: np.mean(exp_data_select[gamma_argmax==x],axis=0)-np.mean(exp_data_select[gamma_argmax!=x],axis=0), gamma_argmax_counts[0])))]
        key_newkey=pd.DataFrame(gamma_argmax_counts_lfc,index=['idx','counts','lfc']).T.astype({'idx':int,'counts':int}).set_index('idx').sort_values(by='lfc',ascending=False).index.tolist()
    gamma_argmax=[key_newkey.index(argmax) for argmax in gamma_argmax]

    return gamma_argmax


# In[ ]:


def gamma_list_exp_data_to_gamma_argmax_list(gamma_list,exp_data=None):
    
    pool=multiprocessing.Pool(processes=16)
    
    if exp_data is None:
        gamma_argmax_list=pool.map(gamma_exp_to_gamma_argmax,gamma_list)
    else:
        gamma_argmax_list=pool.starmap(gamma_exp_to_gamma_argmax,[(gamma_list[i],exp_data[i]) for i in range(len(gamma_list))])
    
    pool.close()
    pool.join()
    
    return np.array(gamma_argmax_list)

"""
def gamma_list_exp_data_to_gamma_argmax_list2(gamma_list,exp_data=None):
    
    pool=multiprocessing.Pool(processes=16)
    
    if exp_data is None:
        gamma_argmax_list=pool.map(gamma_exp_to_gamma_argmax,gamma_list)
    else:
        gamma_argmax_list=pool.starmap(gamma_exp_to_gamma_argmax2,[(gamma_list[i],exp_data[i]) for i in range(len(gamma_list))])
    
    pool.close()
    pool.join()
    
    return np.array(gamma_argmax_list)
"""    


# In[4]:


def gamma_argmax_list_to_minorsize_list_list(gamma_argmax_list):
    minorsize_list=np.sum(gamma_argmax_list==0,axis=1)
    print(minorsize_list)
    minorsize_list_list=[np.clip(minorsize_list, a_min=0, a_max=minorsize) for minorsize in minorsize_list]
    
    return np.array(minorsize_list_list)


# In[5]:


def gamma_argmax_list_to_intersection(gamma_argmax_list,idx):
    intersection=np.sum((gamma_argmax_list[idx]==gamma_argmax_list)&(gamma_argmax_list[idx]==0),axis=1)    
    return intersection


# In[ ]:


def gamma_argmax_list_to_intersection_list(gamma_argmax_list):
    pool=multiprocessing.Pool(processes=16)
    
    intersection_list=pool.starmap(gamma_argmax_list_to_intersection,[(gamma_argmax_list,i) for i in np.arange(gamma_argmax_list.shape[0])])

    pool.close()
    pool.join()    
    
    return np.array(intersection_list)


# In[ ]:





# In[ ]:





# In[ ]:


if __name__ == '__main__':

    #from scipy.io import mmread
    #import numpy as np
    #import pandas as pd
    #Y_=mmread('../datasets/koh_extract/koh.data.counts.mm').toarray().astype(float).transpose()
    #s_=pd.read_csv('../datasets/analysis/koh.size_factor_cluster.tsv',sep='\t',header=None)[0].values.astype(float)#.reshape(-1,1)
    #X_=np.array([np.ones(Y_.shape[0])]).transpose()    
    
    device=torch.device('cuda:2')
    
    Y_=np.ones((446,4898))
    X_=np.ones((446,1))
    s_=np.ones((446))
    
    get_QQscore(Y=Y_, X=X_, s=s_, num_cluster_list=[1,2,3], LR=0.1, EM_ITER_MAX=20, M_ITER_MAX=10000,LL_diff_tolerance=1e-4, Q_diff_tolerance=1e-4, device=device, verbose=True)

