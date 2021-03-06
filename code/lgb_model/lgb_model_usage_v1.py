from scipy import sparse
from numpy import array
from scipy.sparse import csr_matrix
import os
import copy
import datetime
import warnings
import pandas as pd
import numpy as np
import math
from datetime import datetime
import random
import gc
import time

from sklearn.model_selection import train_test_split, StratifiedKFold
from matplotlib import pyplot
import matplotlib as mpl
import seaborn as sns
import lightgbm as lgb
import matplotlib.pyplot as plt

from sklearn.externals import joblib
from sklearn.metrics import f1_score
from sklearn.metrics import accuracy_score
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.decomposition import TruncatedSVD


###############################################
########## 数据加载
###############################################
# 导入usage的样本标签
age_train = pd.read_csv('../../data/processed_data/age_train_usage.csv',dtype={'uId':np.int32, 'age_group':np.int8})
age_test = pd.read_csv('../../data/processed_data/age_test_usage.csv',dtype={'uId':np.int32})

# 导入基础表特征
base_train = sparse.load_npz('../../data/csr_features_usage/base_train_usage.npz')
base_test = sparse.load_npz('../../data/csr_features_usage/base_test_usage.npz')

# 导入激活表TFIDF特征
actived_app_tfidf_train_3000 = sparse.load_npz('../../data/csr_features_usage/actived_app_tfidf_train_3000_usage.npz')
actived_app_tfidf_test_3000 = sparse.load_npz('../../data/csr_features_usage/actived_app_tfidf_test_3000_usage.npz')

# 导入激活表统计特征
actived_features_train = sparse.load_npz('../../data/csr_features_usage/actived_features_train_usage.npz')
actived_features_test = sparse.load_npz('../../data/csr_features_usage/actived_features_test_usage.npz')

# 导入usage表统计特征
usage_features_train = sparse.load_npz('../../data/csr_features_usage/usage_features_train.npz')
usage_features_test = sparse.load_npz('../../data/csr_features_usage/usage_features_test.npz')

###############################################
########## csr格式特征拼接
###############################################
train = sparse.hstack((base_train,actived_app_tfidf_train_3000))
test = sparse.hstack((base_test,actived_app_tfidf_test_3000))
print(train.shape)
print(test.shape)
del base_train,base_test,actived_app_tfidf_train_3000,actived_app_tfidf_test_3000
gc.collect()

train = sparse.hstack((train,actived_features_train))
test = sparse.hstack((test,actived_features_test))
print(train.shape)
print(test.shape)
del actived_features_train,actived_features_test
gc.collect()

train = sparse.hstack((train,usage_features_train))
test = sparse.hstack((test,usage_features_test))
print(train.shape)
print(test.shape)
del usage_features_train,usage_features_test
gc.collect()


###############################################
########## 参数设置
###############################################
# lgb 参数
lgb_params = {
    "boosting_type": "gbdt",
    "objective": "multiclass",
    'metric': {'multi_logloss','multi_error'},
    "learning_rate": 0.1,
    "max_depth": 7,
    "num_leaves": 105,
    "num_class": 6,
    "feature_fraction": 0.7,
    "bagging_fraction": 0.8,     
    'min_data_in_leaf': 500,
    'bagging_freq': 1, 
    "nthread":20
}
###############################################
########## 模型训练
###############################################
start_time = time.time()

train = train.tocsr()
test = test.tocsr()
label = age_train.age_group-1
label = label.values
train_uid = age_train.uId
test_uid = age_test.uId
n_splits = 5    # 分为5折
seed = 2019     # 随机种子

# 采取k折模型方案
best_score = []    # 交叉验证各折的准确度
y_test = np.zeros((test.shape[0],6))
y_val = np.zeros((train.shape[0],6))
skf = StratifiedKFold(n_splits=n_splits, random_state=seed, shuffle=True)

# 交叉验证
for index, (train_index, valid_index) in enumerate(skf.split(train, label)):
    print(index)
    X_train, X_valid, y_train, y_valid = train[train_index], train[valid_index], label[train_index], label[valid_index]
    train_data = lgb.Dataset(X_train, label=y_train)    # 训练数据
    valid_data = lgb.Dataset(X_valid, label=y_valid)    # 验证数据
    model = lgb.train(lgb_params, train_data, num_boost_round=1000, valid_sets=[valid_data],early_stopping_rounds=100, verbose_eval=1)     # 训练
    del X_train,train_data,valid_data
    gc.collect()
    joblib.dump(model, "../../data/output/lgb_model_usage_csr_v1_{}.m".format(index))      # 保存模型
    # model = joblib.load("../../data/output/lgb_model_full_csr_v1_{}.m".format(index))     # 加载模型
    y_val[valid_index] = model.predict(X_valid, num_iteration=model.best_iteration)  # 预测验证集
    best_score.append(accuracy_score(np.argmax(y_val[valid_index],axis=1),y_valid))  # 计算准确度
    print(best_score)
    gc.collect()
    y_test +=  np.array(model.predict(test, num_iteration=model.best_iteration))/5  # 预测测试集
    del X_valid,y_train,y_valid
    gc.collect()    

# 保存验证集概率
y_val = pd.DataFrame(y_val)
y_val = pd.concat([train_uid,y_val],axis=1)
y_val.to_csv('../../data/output/lgb_valid_usage_csr_v1.csv', index=False, encoding='utf-8')
# 保存测试集概率
y_test = pd.DataFrame(y_test)
y_test = pd.concat([test_uid,y_test],axis=1)
y_test.to_csv('../../data/output/lgb_test_usage_csr_v1.csv', index=False, encoding='utf-8')
# 保存每个模型验证集对应的分数
best_score = pd.DataFrame(best_score)
best_score.to_csv('../../data/output/lgb_model_score_usage_csr_v1.csv', index=False, encoding='utf-8')
print("OK")
end_time = time.time()
print('模型训练所秏分钟：', (end_time-start_time)/60)