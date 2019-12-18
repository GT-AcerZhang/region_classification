# -*- coding: utf-8 -*-
import time
import numpy as np
import sys
import datetime
import pandas as pd
import os
from multiprocessing import Process
from Config import config

# base_path = "/home/download-20190701/"
base_path = config.main_data_path
train_feature_out_path = config.train_feature_out_path  # './feature/train/'
train_table_path = config.train_table_path  # main_data_path + 'train.txt'
train_main_visit_path = config.train_main_visit_path  # main_data_path + "train_visit/train/"

test_feature_out_path = config.test_feature_out_path  # './feature/test/'
test_table_path = config.test_table_path  # main_data_path + 'test.txt'
test_main_visit_path = config.test_main_visit_path  # main_data_path + "test_visit/test/"

train_num = 400000
test_num = 100000
file_num_each_job_train = 10000
file_num_each_job_test = 2500
workers_train = int(train_num / file_num_each_job_train)
workers_test = int(test_num / file_num_each_job_test)

user_place_visit_num, user_place_user_num = {}, {}
# user_place_visit_num_day = {}
# user_place_user_num_day = {}
user_place_visit_num_hour = {}
user_place_user_num_hour = {}
# user_place_visit_num_holiday = {}
# user_place_user_num_holiday = {}

hoilday_map = {
    '6_5': 1,
    '1_12': 2,
    '1_13': 3,
    '0_18': 4,
    '1_18': 5,
    '1_20': 6,
}

TEST_FLAG = False

# 用字典查询代替类型转换，可以减少一部分计算时间
date2position = {}
datestr2dateint = {}
str2int = {}
for i in range(24):
    str2int[str(i).zfill(2)] = i

# 访问记录内的时间从2018年10月1日起，共182天
# 将日期按日历排列
for i in range(182):
    date = datetime.date(day=1, month=10, year=2018) + datetime.timedelta(days=i)
    date_int = int(date.__str__().replace("-", ""))
    date2position[date_int] = [i % 7, i // 7]
    datestr2dateint[str(date_int)] = date_int


def visit2array(table):
    strings = table[1]
    init = np.zeros((7, 26, 24))
    for string in strings:
        # print(string)
        temp = []
        for item in string.split(','):
            temp.append([item[0:8], item[9:].split("|")])
        for date, visit_lst in temp:
            # x - 第几周
            # y - 第几天
            # z - 几点钟
            # value - 到访的总人数
            x, y = date2position[datestr2dateint[date]]
            for visit in visit_lst:  # 统计到访的总人数
                init[x][y][str2int[visit]] += 1
    return init


def one_hot(x, length):
    tmp = np.zeros(length)
    tmp[x] = 1
    return tmp


def extract_user(user_init):
    # user_init (user, week, day, time)
    # 26周，每周中某一天出现的不同总人数，比如周一出现的不同总人数，周二出现的不同总人数
    day_num = np.zeros((26, 7))
    # 7天，一天中某一小时出现的不同总人数，比如周一出现的不同总人数，周二出现的不同总人数
    time_num = np.zeros((7, 24))
    for user_data in user_init:
        for k in range(24):
            flag = 0
            for i in range(7):
                for j in range(26):
                    if user_data[i, j, k] > 0:
                        flag = 1
                        break
                time_num[i, k] += flag

        for i in range(7):
            flag = 0
            for j in range(26):
                for k in range(24):
                    if user_data[i, j, k] > 0:
                        flag = 1
                        break
                day_num[j, i] += flag

    # print(day_num.flatten())
    ans = []
    ans += list(day_num.flatten())
    ans += list(time_num.flatten())
    ans += [np.max(day_num), np.min(day_num), np.mean(day_num)]
    ans += [np.max(time_num), np.min(time_num), np.mean(time_num)]

    day_num_sum = np.sum(day_num, axis=0)
    # print(day_num, day_num_sum)
    time_num_sum = np.sum(time_num, axis=0)
    # print(time_num.shape, time_num_sum.shape)
    ans += list(day_num_sum)
    ans += list(time_num_sum)
    ans += [np.max(day_num_sum), np.min(day_num_sum), np.mean(day_num_sum), np.var(day_num_sum), np.median(day_num_sum)]
    ans += [np.max(time_num_sum), np.min(time_num_sum), np.mean(time_num_sum), np.var(time_num_sum),
            np.median(time_num_sum)]
    return ans


def user_information(table, label=None, flag=1):
    users = table[0]
    strings = table[1]
    user_place_visit_hour_ = []
    user_place_user_hour_ = []
    for user, string in zip(users, strings):
        # print(user, string)
        # init = np.zeros((7, 26, 24))
        if flag == 1:
            if user not in user_place_visit_num_hour:
                continue
        else:
            if user not in user_place_user_num_hour:
                continue
        temp = []
        for item in string.split(','):
            temp.append([item[0:8], item[9:].split("|")])
        num = 0
        if flag == 1:
            user_place_visit_num_hour_ = np.zeros((4, 9))
        else:
            user_place_user_num_hour_ = np.zeros((4, 9))
        jian_visit = np.zeros((4, 9))
        jian_user = np.zeros((4, 9))
        for date, visit_lst in temp:
            hour_user = np.zeros(4)
            for visit in visit_lst:  # 统计到访的总人数
                z = str2int[visit]
                hour_user[int(z / 6)] = 1
                if label is not None:
                    jian_visit[int(z / 6), label] += 1
            for z in range(4):
                if label is not None:
                    jian_user[z, label] += hour_user[z]

        for date, visit_lst in temp:
            # x - 第几周
            # y - 第几天
            # z - 几点钟
            # value - 到访的总人数
            x, y = date2position[datestr2dateint[date]]
            num += len(visit_lst)
            hour_user = np.zeros(4)

            for visit in visit_lst:  # 统计到访的总人数
                z = str2int[visit]
                # init[x][y][z] += 1
                hour_user[int(z / 6)] = 1
                if flag == 1:
                    user_place_visit_num_hour_[int(z / 6)] += user_place_visit_num_hour[user][int(z / 6)]
                    if label is not None:
                        user_place_visit_num_hour_[int(z / 6), label] -= jian_visit[int(z/6), label]
                else:
                    user_place_user_num_hour_[int(z/6)] += user_place_user_num_hour[user][int(z/6)]
                    if label is not None:
                        user_place_user_num_hour_[int(z/6), label] -= jian_user[int(z/6), label]

        # user_init.append(init)
        # user_nums.append(num)
        if flag == 1:
            if user in user_place_visit_num_hour:
                if np.sum(user_place_visit_num_hour_) == 0:
                    continue
                user_place_visit_hour_.append(user_place_visit_num_hour_)
        else:
            if user in user_place_user_num_hour:
                if np.sum(user_place_user_num_hour_) == 0:
                    continue
                user_place_user_hour_.append(user_place_user_num_hour_)
    user_place_visit_hour_ = np.array(user_place_visit_hour_)
    user_place_user_hour_ = np.array(user_place_user_hour_)
    if len(user_place_visit_hour_) == 0:
        user_place_visit_hour_ = np.zeros((1, 4, 9))
    if len(user_place_user_hour_) == 0:
        user_place_user_hour_ = np.zeros((1, 4, 9))

    features = []
    if flag == 1:
        features += list(np.mean(user_place_visit_hour_, axis=0).flatten())
        features += list(np.sum(user_place_visit_hour_, axis=0).flatten())
        features += list(np.std(user_place_visit_hour_, axis=0).flatten())
        features += list(np.median(user_place_visit_hour_, axis=0).flatten())
        features += list(np.max(user_place_visit_hour_, axis=0).flatten())
        features += list(np.min(user_place_visit_hour_, axis=0).flatten())
        features + list(np.percentile(user_place_visit_hour_, 25, axis=0).flatten())
        features + list(np.percentile(user_place_visit_hour_, 75, axis=0).flatten())
    else:
        features += list(np.mean(user_place_user_hour_, axis=0).flatten())
        features += list(np.sum(user_place_user_hour_, axis=0).flatten())
        features += list(np.std(user_place_user_hour_, axis=0).flatten())
        features += list(np.median(user_place_user_hour_, axis=0).flatten())
        features += list(np.max(user_place_user_hour_, axis=0).flatten())
        features += list(np.min(user_place_user_hour_, axis=0).flatten())
        features + list(np.percentile(user_place_user_hour_, 25, axis=0).flatten())
        features + list(np.percentile(user_place_user_hour_, 75, axis=0).flatten())

    return features, users


def static_user_place_num(num):
    user_place_visit_num_hour = {}
    user_place_user_num_hour = {}
    # table = pd.read_csv(base_path + "train_44w.txt", header=None)
    table = pd.read_csv(train_table_path, header=None)
    filenames = [a[0].split("/")[-1].split('.')[0] for a in table.values]
    for index, filename in enumerate(filenames[num * file_num_each_job_train: (num + 1) * file_num_each_job_train]):
        if TEST_FLAG and index > 2:
            break
        table = pd.read_table(base_path + "train_visit/" + filename + ".txt", header=None)
        label = int(filename.split("_")[1]) - 1
        users = table[0]
        strings = table[1]
        for user, string in zip(users, strings):
            # if user not in user_place_visit_num_holiday:
            #     user_place_visit_num_holiday[user] = np.zeros((7, 9))
            # if user not in user_place_user_num_holiday:
            #     user_place_user_num_holiday[user] = np.zeros((7, 9))
            # if user not in user_place_visit_num_day:
            #     user_place_visit_num_day[user] = np.zeros((7, 9))
            # if user not in user_place_user_num_day:
            #     user_place_user_num_day[user] = np.zeros((7, 9))
            if user not in user_place_visit_num_hour:
                user_place_visit_num_hour[user] = np.zeros((4, 9))
            if user not in user_place_user_num_hour:
                user_place_user_num_hour[user] = np.zeros((4, 9))
            # print(user, string)
            temp = []
            for item in string.split(','):
                temp.append([item[0:8], item[9:].split("|")])
            num = 0

            for date, visit_lst in temp:
                # x - 第几周
                # y - 第几天
                # z - 几点钟
                # value - 到访的总人数
                x, y = date2position[datestr2dateint[date]]
                num += len(visit_lst)
                hour_user = np.zeros(4)
                for visit in visit_lst:  # 统计到访的总人数
                    z = str2int[visit]
                    hour_user[int(z / 6)] = 1
                    user_place_visit_num_hour[user][int(z / 6), label] += 1
                for z in range(4):
                    user_place_user_num_hour[user][z, label] += hour_user[z]

    ans = [user_place_visit_num_hour, user_place_user_num_hour]
    return ans


def f(a, b, c, d):
    return d+c*10000+b*10000*10000+a*10000*10000*10000


def inv_f(x):
    d = x % 10000
    c = int(x/10000)%10000
    b = int(x/(10000*10000))%10000
    a = int(x/(10000*10000*10000))
    return a, b, c, d


def static_user_place_num_(flag=1):
    user_place_visit_num_hour = {}
    user_place_user_num_hour = {}
    # table = pd.read_csv(base_path + "train_44w.txt", header=None)
    table = pd.read_csv(train_table_path, header=None)
    filenames = [a[0].split("/")[-1].split('.')[0] for a in table.values]
    for index, filename in enumerate(filenames):
        if TEST_FLAG and index > 2:
            break
        table = pd.read_table(base_path + "train_visit/" + filename + ".txt", header=None)
        label = int(filename.split("_")[1]) - 1
        users = table[0]
        strings = table[1]
        for user, string in zip(users, strings):
            # if user not in user_place_visit_num_holiday:
            #     user_place_visit_num_holiday[user] = np.zeros((7, 9))
            # if user not in user_place_user_num_holiday:
            #     user_place_user_num_holiday[user] = np.zeros((7, 9))
            # if user not in user_place_visit_num_day:
            #     user_place_visit_num_day[user] = np.zeros((7, 9))
            # if user not in user_place_user_num_day:
            #     user_place_user_num_day[user] = np.zeros((7, 9))
            if flag == 1:
                if user not in user_place_visit_num_hour:
                    user_place_visit_num_hour[user] = np.zeros((4, 9), dtype='int16')
            else:
                if user not in user_place_user_num_hour:
                    user_place_user_num_hour[user] = np.zeros((4, 9), dtype='int16')
            # user_place_visit_num_hour_tmp = np.zeros((9, 4))
            # user_place_user_num_hour_tmp = np.zeros((9, 4))
            # print(user, string)
            temp = []
            for item in string.split(','):
                temp.append([item[0:8], item[9:].split("|")])
            num = 0

            for date, visit_lst in temp:
                # x - 第几周
                # y - 第几天
                # z - 几点钟
                # value - 到访的总人数
                x, y = date2position[datestr2dateint[date]]
                num += len(visit_lst)
                hour_user = np.zeros(4)
                for visit in visit_lst:  # 统计到访的总人数
                    z = str2int[visit]
                    hour_user[int(z / 6)] = 1
                    if flag == 1:
                        user_place_visit_num_hour[user][int(z / 6), label] += 1
                if flag != 1:
                    for z in range(4):
                        user_place_user_num_hour[user][z, label] += hour_user[z]

    ans = [user_place_visit_num_hour, user_place_user_num_hour]
    return ans


def visit2array_train_(flag=1):
    # table = pd.read_csv(base_path + "train_44w.txt", header=None)
    table = pd.read_csv(train_table_path, header=None)
    filenames = [a[0].split("/")[-1].split('.')[0] for a in table.values]
    length = len(filenames)
    start_time = time.time()
    # total_users = set()
    all_features = []
    for index, filename in enumerate(filenames):
        if TEST_FLAG and index > 2:
            break
        table = pd.read_table(base_path + "train_visit/" + filename + ".txt", header=None)
        # array = visit2array(table)
        label = int(filename.split("_")[1]) - 1
        features, users = user_information(table, label=label, flag=flag)
        # users = set(users)
        # tmp = total_users & users
        # print(tmp)
        # total_users = total_users | users
        # np.save("./data/train_visit/" + filename + ".npy", array)
        # print(array)
        sys.stdout.write('\r>> Processing visit data %d' % (index + 1))
        # sys.stdout.flush()
        all_features.append(np.array(features))
    # sys.stdout.write('\n')
    print("using time:%.2fs" % (time.time() - start_time))
    return all_features


def visit2array_train(num):
    # table = pd.read_csv(base_path + "train_44w.txt", header=None)
    table = pd.read_csv(train_table_path, header=None)
    filenames = [a[0].split("/")[-1].split('.')[0] for a in table.values]
    length = len(filenames)
    start_time = time.time()
    # total_users = set()
    all_features = []
    for index, filename in enumerate(filenames[num * file_num_each_job_train: (num + 1) * file_num_each_job_train]):
        if TEST_FLAG and index > 2:
            break
        table = pd.read_table(base_path + "train_visit/" + filename + ".txt", header=None)
        # array = visit2array(table)
        label = int(filename.split("_")[1]) - 1
        features, users = user_information(table, label=label)
        # users = set(users)
        # tmp = total_users & users
        # print(tmp)
        # total_users = total_users | users
        # np.save("./data/train_visit/" + filename + ".npy", array)
        # print(array)
        sys.stdout.write('\r>> Processing visit data %d' % (index + 1))
        # sys.stdout.flush()
        all_features.append(features)
    # sys.stdout.write('\n')
    print("using time:%.2fs" % (time.time() - start_time))
    return all_features


def visit2array_test(num):
    # table = pd.read_csv(base_path + "test.txt", header=None)
    table = pd.read_csv(test_table_path, header=None)
    filenames = [a[0].split("/")[-1].split('.')[0] for a in table.values]
    length = len(filenames)
    start_time = time.time()
    # total_users = set()
    all_features = []
    for index, filename in enumerate(filenames[num * file_num_each_job_test: (num + 1) * file_num_each_job_test]):
        if TEST_FLAG and index > 2:
            break
        table = pd.read_table(base_path + "test_visit/" + filename + ".txt", header=None)
        # array = visit2array(table)
        features, users = user_information(table)
        # users = set(users)
        # tmp = total_users & users
        # print(tmp)
        all_features.append(features)
        # total_users = total_users | users
        # np.save("./data/train_visit/" + filename + ".npy", array)
        # print(array)
        sys.stdout.write('\r>> Processing visit data %d/%d' % (index + 1, length))
        # sys.stdout.flush()
    # sys.stdout.write('\n')
    print("using time:%.2fs" % (time.time() - start_time))
    return all_features


def visit2array_test_(flag=1):
    # table = pd.read_csv(base_path + "test.txt", header=None)
    table = pd.read_csv(test_table_path, header=None)
    filenames = [a[0].split("/")[-1].split('.')[0] for a in table.values]
    length = len(filenames)
    start_time = time.time()
    # total_users = set()
    all_features = []
    for index, filename in enumerate(filenames):
        if TEST_FLAG and index > 2:
            break
        table = pd.read_table(base_path + "test_visit/" + filename + ".txt", header=None)
        # array = visit2array(table)
        features, users = user_information(table, flag=flag)
        # users = set(users)
        # tmp = total_users & users
        # print(tmp)
        all_features.append(np.array(features))
        # total_users = total_users | users
        # np.save("./data/train_visit/" + filename + ".npy", array)
        # print(array)
        sys.stdout.write('\r>> Processing visit data %d/%d' % (index + 1, length))
        # sys.stdout.flush()
    # sys.stdout.write('\n')
    print("using time:%.2fs" % (time.time() - start_time))
    return all_features


def write_feature(feature, fname):
    np.save(fname, feature)
    # np.savetxt(fname, feature, delimiter=',', fmt='%.4e')


def run_train_feature(num):
    train_features = visit2array_train(num)
    write_pkl(data=train_features, fname='./data/tmp/train_feature_{}.pkl'.format(num))


def run_test_feature(num):
    test_feature = visit2array_test(num)
    write_pkl(data=test_feature, fname='./data/tmp/test_feature_{}.pkl'.format(num))


def run_statistic(num):
    ans = static_user_place_num(num)
    write_pkl(data=ans[0], fname='./data/tmp/user_place_visit_num_hour_{}.pkl'.format(num))
    write_pkl(data=ans[1], fname='./data/tmp/user_place_user_num_hour_{}.pkl'.format(num))


def write_pkl(data, fname):
    import pickle
    pickle.dump(data, open(fname, 'wb'))


def get_final_statistic(workers=workers_train, flag=1):
    import pickle
    global user_place_visit_num_hour
    global user_place_user_num_hour
    if flag == 1:
        if os.path.exists('./data/tmp/user_place_visit_num_hour_44w.pkl'):
            user_place_visit_num_hour = pickle.load(open('./data/tmp/user_place_visit_num_hour_44w.pkl', 'rb'))
        else:
            for i in range(workers):
                user_place_visit_num_hour_tmp = pickle.load(
                    open('./data/tmp/user_place_visit_num_hour_{}.pkl'.format(i), 'rb'))
                for user in user_place_visit_num_hour_tmp:
                    if user not in user_place_visit_num_hour:
                        user_place_visit_num_hour[user] = user_place_visit_num_hour_tmp[user]
                    else:
                        user_place_visit_num_hour[user] += user_place_visit_num_hour_tmp[user]
            write_pkl(user_place_visit_num_hour, fname='./data/tmp/user_place_visit_num_hour.pkl')
    else:
        if os.path.exists('./data/tmp/user_place_user_num_hour_44w.pkl'):
            user_place_user_num_hour = pickle.load(open('./data/tmp/user_place_user_num_hour_44w.pkl', 'rb'))
        else:
            for i in range(workers):
                user_place_user_num_hour_tmp = pickle.load(
                    open('./data/tmp/user_place_user_num_hour_{}.pkl'.format(i), 'rb'))
                for user in user_place_user_num_hour_tmp:
                    if user not in user_place_user_num_hour:
                        user_place_user_num_hour[user] = user_place_user_num_hour_tmp[user]
                    else:
                        user_place_user_num_hour[user] += user_place_user_num_hour_tmp[user]
            write_pkl(user_place_user_num_hour, fname='./data/tmp/user_place_user_num_hour.pkl')


job_num = 10


def run_1(flag=1):
    # WORKERS = 40
    if flag == 1:
        ans = static_user_place_num_(flag=1)
        write_pkl(data=ans[0], fname='./data/tmp/user_place_visit_num_hour_44w.pkl')
        del ans
    else:
        ans = static_user_place_num_(flag=2)
        write_pkl(data=ans[1], fname='./data/tmp/user_place_user_num_hour_44w.pkl')
        del ans
    # threads = []
    #
    # for i in range(workers_train):
    #     p = Process(target=run_statistic, args=[i])
    #     threads.append(p)
    #     p.start()
        # epoch_num = int(workers_train/job_num)
        # if workers_train%job_num != 0:
        #     epoch_num += job_num
        # for j in range(epoch_num):
        #     for i in range(j*job_num, (j+1)*job_num):
        #         p = Process(target=run_statistic, args=[i])
        #         threads.append(p)
        #         p.start()
        #     time.sleep(20 * 60)


def run_2(flag=1):
    global user_place_visit_num_hour
    global user_place_user_num_hour
    if flag == 1:
        get_final_statistic(workers_train, flag=1)
        # print(user_place_user_num, user_place_visit_num)

        train_features = visit2array_train_(flag=1)
        train_features = np.array(train_features)
        write_feature(feature=train_features, fname='./data/tmp/train_feature_user_hour_visit_44w.npy')
        del train_features
        # write_pkl(data=train_features, fname='./data/tmp/train_feature_user_hour.pkl')
        test_features = visit2array_test_(flag=1)
        test_features = np.array(test_features)
        write_feature(feature=test_features, fname='./data/tmp/test_feature_user_hour_visit_44w.npy')
        # write_pkl(data=test_features, fname='./data/tmp/test_feature_user_hour.pkl')
        del test_features
        user_place_visit_num_hour = {}
        user_place_user_num_hour = {}
    else:
        user_place_visit_num_hour = {}
        user_place_user_num_hour = {}
        get_final_statistic(workers_train, flag=2)
        # print(user_place_user_num, user_place_visit_num)

        train_features = visit2array_train_(flag=2)
        train_features = np.array(train_features)
        write_feature(feature=train_features, fname='./data/tmp/train_feature_user_hour_user_44w.npy')
        del train_features
        # write_pkl(data=train_features, fname='./data/tmp/train_feature_user_hour.pkl')
        test_features = visit2array_test_(flag=2)
        test_features = np.array(test_features)
        write_feature(feature=test_features, fname='./data/tmp/test_feature_user_hour_user_44w.npy')
    # write_pkl(data=tes
    # threads = []
    # for i in range(workers_train):
    #     p = Process(target=run_train_feature, args=[i])
    #     threads.append(p)
    #     p.start()


    # for i in range(int(workers_train / 2)):
    # epoch_num = int(workers_train / job_num)
    # if workers_train % job_num != 0:
    #     epoch_num += 1
    # for j in range(epoch_num):
    #     for i in range(j*job_num, (j+1)*job_num):
    #         p = Process(target=run_train_feature, args=[i])
    #         threads.append(p)
    #         p.start()
    #     time.sleep(2 * 60 * 60)

    # for i in range(workers_test):
    #     p = Process(target=run_test_feature, args=[i])
    #     threads.append(p)
    #     p.start()
    # epoch_num = int(workers_test / job_num)
    # if workers_train % job_num != 0:
    #     epoch_num += 1
    #
    # for j in range(epoch_num):
    #     for i in range(j*job_num, (j+1)*job_num):
    #         p = Process(target=run_test_feature, args=[i])
    #         threads.append(p)
    #         p.start()
    # time.sleep(2 * 60 * 60)


# def run_2():
#     get_final_statistic(int(train_num/2000))
#     # print(user_place_user_num, user_place_visit_num)
#     threads = []
#     # for i in range(workers_train):
#     #     p = Process(target=run_train_feature, args=[i])
#     #     threads.append(p)
#     #     p.start()
#     # for i in range(int(workers_train / 2)):
#     epoch_num = int(workers_train / job_num)
#     if workers_train % job_num != 0:
#         epoch_num += 1
#     for j in range(epoch_num):
#         for i in range(j*job_num, (j+1)*job_num):
#             p = Process(target=run_train_feature, args=[i])
#             threads.append(p)
#             p.start()
#         time.sleep(2 * 60 * 60)
#
#     # for i in range(workers_test):
#     #     p = Process(target=run_test_feature, args=[i])
#     #     threads.append(p)
#     #     p.start()
#     epoch_num = int(workers_test / job_num)
#     if workers_train % job_num != 0:
#         epoch_num += 1
#
#     for j in range(epoch_num):
#         for i in range(j*job_num, (j+1)*job_num):
#             p = Process(target=run_test_feature, args=[i])
#             threads.append(p)
#             p.start()
#         # time.sleep(2 * 60 * 60)


def get_final_train_features(workers=workers_train):
    import pickle
    features = []
    for i in range(workers):
        tmp = pickle.load(open('./data/tmp/train_feature_user_hour_{}.pkl'.format(i), 'rb'))
        print(np.array(tmp).shape, np.array(tmp[0]), np.array(tmp[1]))
        features += list(tmp)
    features = np.array(features)
    print(features.shape)
    write_feature(feature=features, fname='./data/tmp/train_feature_user_hour.npy')
    write_pkl(data=features, fname='./data/tmp/train_feature_user_hour.pkl')
    return features


def get_final_test_features(workers=workers_test):
    import pickle
    features = []
    for i in range(workers):
        tmp = pickle.load(open('./data/tmp/test_feature_user_hour_{}.pkl'.format(i), 'rb'))
        features += list(tmp)
    features = np.array(features)
    print(features.shape)
    write_feature(feature=features, fname='./data/tmp/test_feature_user_hour.npy')
    write_pkl(data=features, fname='./data/tmp/test_feature_user_hour.pkl')
    return features


if __name__ == '__main__':
    if not os.path.exists("./data/tmp/"):
        os.makedirs("./data/tmp/")

    # 三步需要分开运行
    # 第一步
    run_1(flag=1)
    # 第二步
    run_2(flag=1)

    # 第一步
    run_1(flag=2)
    # 第二步
    run_2(flag=2)
