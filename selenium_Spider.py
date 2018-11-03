from selenium import webdriver
from selenium.webdriver.firefox.options import Options
import pymongo
import time
import scrapy
from scrapy.http import HtmlResponse
from pkg_resources import resource_filename
import re
from ..utils.tyc_text_tool import TycTextTool
import logging
import functools
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import os
from openpyxl import Workbook
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

class TianYanChaSpider(scrapy.Spider):
    name = 'TYC2'
    domain = 'www.tianyancha.com'
    custom_settings = {
        'LOG_LEVEL': 'INFO'
    }

    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.basedir = resource_filename('cdscrawler', 'resource')
        # mongo db
        self.client = pymongo.MongoClient(host='39.***.54.9', port=27017)
        self.db = self.client['***']
        self.db.authenticate('***','******')
        self.itjuzi_collect = self.db['itjuzi_companies']
        self.collection = self.db['companies']
        self.targetURL = 'https://www.tianyancha.com/search?key='
        # self.options = Options()
        # self.options.add_argument("--headless")
        # self.driver = webdriver.Firefox(options=self.options)
        self.driver = webdriver.Firefox()
        # 策略设置
        self.load_policy()
        self.MAX_AUTO_RECONNECT_ATTEMPTS = 5    # 重试次数

        self.accounts = ['1325202****','1368246***','135107**657']
        self.accountIndex = 0

        # 字体解密
        self.text_tool = TycTextTool()
        self.text_tool.load()
        self.scrap_count = 1

    def reload_driver(self):
        self.scrap_count = 1
        self.driver.close()
        self.options = Options()
        self.options.add_argument("--headless")
        self.driver = webdriver.Firefox(options=self.options)
        # self.driver = webdriver.Firefox()

    # 加载策略
    def load_policy(self):
        # 修改加载策略
        desired_capabilities = DesiredCapabilities.FIREFOX  # 修改页面加载策略
        desired_capabilities['pageLoadStrategy'] = 'none'  # 注释这两行会导致最后输出结果的延迟，即等待页面加载完成再输出
        # 移除图片加载
        profile = webdriver.FirefoxProfile()
        profile.set_preference('permissions.default.image', 2)  # 某些firefox只需要这个
        profile.set_preference('browser.migration.version', 9001)  # 部分需要加上这个
        self.driver.profile = profile
        # 资源加载超时设置
        self.driver.set_page_load_timeout(20)
        self.driver.set_script_timeout(20)


    def getFontKey(self,response):
        # 获取字体加密的key
        if self.isElementExist(response, 'html/body'):
            font_key = response.find_element_by_xpath('html/body').get_attribute('class')
        if font_key:
            match = re.match(r'font-([a-zA-Z0-9]+)', font_key)
            font_key = match.group(1) if match else None
        return font_key

    def login_force(self):
        self.accountIndex = self.accountIndex % 8
        accountName = self.accounts[self.accountIndex]
        if self.isElementExist(self.driver, '//*[@id="web-content"]/div/div/div/div[2]/div/div[2]/div[2]/div[2]/div[2]/input'):
            self.driver.find_element_by_xpath('//*[@id="web-content"]/div/div/div/div[2]/div/div[2]/div[2]/div[2]/div[2]/input').send_keys(accountName)
        if self.isElementExist(self.driver,'//*[@id="web-content"]/div/div/div/div[2]/div/div[2]/div[2]/div[2]/div[3]/input'):
            self.driver.find_element_by_xpath('//*[@id="web-content"]/div/div/div/div[2]/div/div[2]/div[2]/div[2]/div[3]/input').send_keys('aa11**33')
        if self.isElementExist(self.driver,'//*[@id="web-content"]/div/div/div/div[2]/div/div[2]/div[2]/div[2]/div[5]'):
            self.driver.find_element_by_xpath('//*[@id="web-content"]/div/div/div/div[2]/div/div[2]/div[2]/div[2]/div[5]').click()
        self.accountIndex += 1

    def login_check(self):
        WebDriverWait(self.driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div/div[3]/div[1]/a'))).click()
        if self.isElementsExist(self.driver,
                                '//*[@id="_modal_container"]/div/div/div[2]/div/div/div[3]/div[2]/div[1]'):
            self.accountIndex = self.accountIndex % 8
            accountName = self.accounts[self.accountIndex]
            # 等待弹窗
            time.sleep(2.)
            WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="_modal_container"]/div/div/div[2]/div/div/div[3]/div[2]/div[1]'))).click()
            WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="_modal_container"]/div/div/div[2]/div/div/div[3]/div[1]/div[2]/input'))).send_keys(
                accountName)
            WebDriverWait(self.driver, 20).until(EC.visibility_of_element_located(
                (By.XPATH, '//*[@id="_modal_container"]/div/div/div[2]/div/div/div[3]/div[1]/div[3]/input'))).send_keys(
                'aa112233')
            WebDriverWait(self.driver, 20).until(EC.visibility_of_element_located(
                (By.XPATH, '//*[@id="_modal_container"]/div/div/div[2]/div/div/div[3]/div[1]/div[5]'))).click()
            self.accountIndex += 1

    def auto_login(self):
        if 'login' in self.driver.current_url:
            if self.isElementExist(self.driver,'//*[@id="web-header"]/div/div/div[2]/div/div[1]/a'):
                self.login_force()
        else:
            try:
                if self.isElementExist(self.driver, '/html/body/div[1]/div/div[3]/div[1]/a'):
                    if self.driver.find_element_by_xpath('/html/body/div[1]/div/div[3]/div[1]/a').text == '登录/注册':
                        self.login_check()
            except Exception as ex:
                self.logger.info(ex)

    def isClassExist(self,className):
        try:
            self.driver.find_element_by_class_name(className)
            return True
        except:
            return False


    def isElementExist(self,element, path):
        try:
            element.find_element_by_xpath(path)
            return True
        except:
            return False


    def isElementsExist(self,element, path):
        try:
            element.find_elements_by_xpath(path)
            return True
        except:
            return False
    # inser or update
    def upsert(self,company_info):
        self.collection.find_one_and_update({'companyName': company_info['name']}, {'$set': company_info},
                                            upsert=True)
    def update(self,name):
        self.itjuzi_collect.update({'name': name}, {'$set': {'crawled_by_tianyancha': True}})

    def update_itjuzi(self,name):
        result = self.itjuzi_collect.find_one({'name':name},{'nothing_by_tianyancha': 1, '_id': 0})
        if 'nothing_by_tianyancha' in result:
            index = result['nothing_by_tianyancha']
            if index > 1:
                self.graceful_auto_reconnect(self.update)(name)
            else:
                self.itjuzi_collect.update({'name': name},
                                           {'$set': {'nothing_by_tianyancha': index + 1}})
        else:
            self.itjuzi_collect.find_one_and_update({'name': name},{'$set': {'nothing_by_tianyancha':1}})
    # 重试
    def graceful_auto_reconnect(self,mongo_op_func):
        """Gracefully handle a reconnection event."""
        @functools.wraps(mongo_op_func)
        def wrapper(*args, **kwargs):
            for attempt in range(self.MAX_AUTO_RECONNECT_ATTEMPTS):
                try:
                    return mongo_op_func(*args, **kwargs)
                except pymongo.errors.AutoReconnect as e:
                    wait_t = 0.5 * pow(2, attempt)  # exponential back off
                    logging.warning("PyMongo auto-reconnecting... %s. Waiting %.1f seconds.", str(e), wait_t)
                    time.sleep(wait_t)
        return wrapper
    # csv写入
    # 读取txt
    def read_txt(self,path):
        birth_data = []
        with open(path) as file_lines:
            for line in file_lines.readlines():
                birth_data.append(line)
            return birth_data
    # input_data
    def input_dat(self):
        resource_dir = resource_filename('cdscrawler', 'resource')
        resource_file = os.path.join(resource_dir, 'names.txt')
        companie_list = self.read_txt(resource_file)
        output_file = os.path.join(resource_dir,'东莞潜在客户.xlsx')
        wb = Workbook()
        ws = wb.active
        ws.title = 'CIS数据'
        ws.append([
            '公司全称', '核心团队1','核心团队2','核心团队3','核心团队4','核心团队5'
        ])


        for name in companie_list:
            name = name.replace('\n','')
            company = self.collection.find_one({'name': name})
            row = []
            if company == None:
                continue

            tyc = company['company_tianyancha']
            list = tyc['coreteam']
            row.append(name)
            for i in  range(len(list)):
                coreteam = list[i]
                row.append(coreteam['memberName'] + ',' + coreteam['position'] + ',' + coreteam['introduce'])
            ws.append(row)
        wb.save(output_file)

    def start_requests(self):
        index = 1
        for companies in self.collection.find({'company_tianyancha':{'$in':[None,{}]}}).sort('_id').batch_size(5):
        # for companies in self.itjuzi_collect.find({'name': {'$nin': [None, '', '暂未收录'], '$exists': True}, 'nothing_by_tianyancha':{'$lte':3},'crawled_by_tianyancha': {'$ne': True}}).batch_size(5):
        # for companies in self.itjuzi_collect.find({'name': {'$nin': [None, '', '暂未收录'], '$exists': True}, 'nothing_by_tianyancha':{'$lte':3},'crawled_by_tianyancha': {'$ne': True}}).batch_size(5):
            # for companies in self.itjuzi_collect.find({'name': {'$nin': [None, '', '暂未收录'],'$exists': True}}).batch_size(5):
            # if self.scrap_count%3 == 0:
                # self.reload_driver()
            name = companies['companyName']
            # if self.collection.find({'companyName':name,'company_tianyancha': {'$nin': [None, {}]}}).count() == 1:
            #     continue
            url = self.targetURL + name
            try:
                self.driver.get(url)
            except Exception as exc:
                self.logger.info(exc)
                continue
            response_first = HtmlResponse(self.driver.current_url, body=self.driver.page_source, encoding='utf-8', request=None)
            if response_first.status != 200:
                continue

            # 登录检测
            self.auto_login()

            if self.isElementExist(self.driver,'//*[@id="web-content"]/div/div[1]/div/div[3]/div[1]/div/div[2]/div[1]/a'):
                url = self.driver.find_element_by_xpath(
                    '//*[@id="web-content"]/div/div[1]/div/div[3]/div[1]/div/div[2]/div[1]/a').get_attribute('href')
                # self.scrap_count += 1
            else:
                continue
            try:
                self.driver.get(url)
            except Exception as ex:
                self.logger.info(ex)
                continue
            # if len(url):
            #     try:
            #         self.driver.get(url)
            #     except(Exception):
            #         continue
            # else:
            #     continue
            res = HtmlResponse(self.driver.current_url, body=self.driver.page_source, encoding='utf-8', request=None)
            # 基本信息
            item = dict()
            item['companyId'] = str(url).split('/')[-1]

            # font key
            fontKey = self.getFontKey(self.driver)

            if self.isElementExist(self.driver, '//*[@id="company_web_top"]/div[2]/div[2]/div[1]/h1'):
                item['companyName'] = self.driver.find_element_by_xpath(
                    '//*[@id="company_web_top"]/div[2]/div[2]/div[1]/h1').text

            if self.isElementExist(self.driver, '//*[@id="company_web_top"]/div[2]/div[2]/div[5]/div[2]/div[1]'):
                item['companyWeb'] = self.driver.find_element_by_xpath(
                    '//*[@id="company_web_top"]/div[2]/div[2]/div[5]/div[2]/div[1]').text
                item['companyWeb'] = item['companyWeb'] if len(item['companyWeb']) > 0 else '暂无信息'
            item['phone'] = res.xpath(
                '//*[@id="company_web_top"]/div[2]/div[2]/div[5]/div[1]/div[1]/span[3]/script/text()').extract_first()
            if not item['phone']:
                item['phone'] = res.xpath(
                    '//*[@id="company_web_top"]/div[2]/div[2]/div[5]/div[1]/div[1]/span[2]/text()').extract_first()
            item['email'] = res.xpath(
                '//*[@id="company_web_top"]/div[2]/div[2]/div[5]/div[1]/div[2]/span[3]/script/text()').extract_first()
            if not item['email']:
                item['email'] = res.xpath(
                    '//*[@id="company_web_top"]/div[2]/div[2]/div[5]/div[1]/div[2]/span[2]/text()').extract_first()
            item['region'] = res.xpath(
                '//*[@id="company_web_top"]/div[2]/div[2]/div[5]/div[2]/div[2]/span[3]/script/text()').extract_first()
            if not item['region']:
                item['region'] = res.xpath(
                    '//*[@id="company_web_top"]/div[2]/div[2]/div[5]/div[2]/div[2]/span[2]/text()').extract_first()
            item['profile'] = res.xpath('//*[@id="company_base_info_detail"]/text()').extract_first()
            if not item['profile']:
                item['profile'] = res.xpath(
                    '//*[@id="company_web_top"]/div[2]/div[2]/div[5]/div[3]/span[2]/text()').extract_first()

            isHighNew = False
            if self.isElementsExist(self.driver, '//*[@id="company_web_top"]/div[2]/div[2]/div'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="company_web_top"]/div[2]/div[2]/div'):
                    if self.isElementExist(sel, '.'):
                        if sel.find_element_by_xpath('.').text == '高新企业':
                            isHighNew = True
            item['isHighNew'] = '1' if isHighNew else '0'

            item['data_source'] = 'tianyancha'

            labelsList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_firmProduct"]/div/a'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_firmProduct"]/div/a'):
                    temp = dict()
                    if self.isElementExist(sel, './div[2]/div[1]'):
                        temp['productName'] = sel.find_element_by_xpath('./div[2]/div[3]').text
                    if self.isElementExist(sel, './div[1]/div[2]/img'):
                        temp['productLogo'] = sel.find_element_by_xpath('./div[1]/div[2]/img').get_attribute('data-src')
                    if self.isElementExist(sel, './div[2]/div[2]'):
                        temp['productProfile'] = sel.find_element_by_xpath('./div[2]/div[2]').text
                    if self.isElementExist(sel, './div[2]/div[3]'):
                        temp['productIndustry'] = sel.find_element_by_xpath('./div[2]/div[3]').text
                    labelsList.append(temp)
            item['labelDes'] = labelsList

            # 企业业务
            business_list = []
            ps = res.xpath('//*[@id="_container_firmProduct"]/div/a')
            for a in ps:
                business = dict()
                attr = a.xpath('./@onclick').extract_first()
                if attr:
                    pid = re.match(r'goToBrand\([\'"]([a-zA-Z0-9]*)', attr)
                    if pid:
                        pid = pid.group(1)
                    business['productId'] = pid
                business['productName'] = a.xpath('./div[2]/div[1]/text()').extract_first()
                business['productLogo'] = a.xpath('./div[1]/div[2]/img/@data-src').extract_first()
                business['summary'] = a.xpath('./div[2]/div[2]/text()').extract_first()
                business['industry'] = a.xpath('./div[2]/div[3]/text()').extract_first()
                business_list.append(dict(business))

            # 资本信息
            capitalItem = dict()
            if self.isElementExist(self.driver,
                                   '//*[@id="_container_baseInfo"]/table[1]/tbody/tr[1]/td[1]/div/div[1]/div[2]/div[1]/a'):
                capitalItem['legalPerson'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[1]/tbody/tr[1]/td[1]/div/div[1]/div[2]/div[1]/a').text
            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[1]/tbody/tr[1]/td[2]/div[2]/text'):
                capitalItem['registeredCapital'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[1]/tbody/tr[1]/td[2]/div[2]/text').text
                capitalItem['registeredCapital'] = self.text_tool.recover(fontKey, capitalItem['registeredCapital'])

            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[1]/tbody/tr[2]/td/div[2]/text'):
                capitalItem['registeredTime'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[1]/tbody/tr[2]/td/div[2]/text').text
                capitalItem['registeredTime'] = self.text_tool.recover(fontKey, capitalItem['registeredTime'])
            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[1]/tbody/tr[3]/td/div[2]'):
                capitalItem['companyStatus'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[1]/tbody/tr[3]/td/div[2]').text

            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[1]/td[2]'):
                capitalItem['registrationNumber'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[1]/td[2]').text
            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[1]/td[4]'):
                capitalItem['organizationCode'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[1]/td[4]').text

            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[2]/td[2]'):
                capitalItem['creditCode'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[2]/td[2]').text
            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[3]/td[2]'):
                capitalItem['taxpayerNumber'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[3]/td[2]').text

            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[3]/td[4]'):
                capitalItem['industry'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[3]/td[4]').text
            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[4]/td[2]'):
                capitalItem['businessTime'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[4]/td[2]').text
            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[4]/td[4]'):
                capitalItem['approvalDate'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[4]/td[4]').text
                capitalItem['approvalDate'] = self.text_tool.recover(fontKey, capitalItem['approvalDate'])
            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[5]/td[4]'):
                capitalItem['personnelScale'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[5]/td[4]').text

            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[6]/td[2]'):
                capitalItem['paidCapital'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[6]/td[2]').text
            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[6]/td[4]'):
                capitalItem['registerOfficer'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[6]/td[4]').text

            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[7]/td[2]'):
                capitalItem['insuredNumber'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[7]/td[2]').text
            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[7]/td[4]'):
                capitalItem['englishName'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[7]/td[4]').text

            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[8]/td[2]'):
                capitalItem['registeredAddress'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[8]/td[2]').text
            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[9]/td[2]'):
                capitalItem['managementRange'] = self.driver.find_element_by_xpath('//*[@id="_container_baseInfo"]/table[2]/tbody/tr[9]/td[2]').text

            if self.isElementExist(self.driver, '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[2]/td[4]'):
                capitalItem['companyType'] = self.driver.find_element_by_xpath(
                    '//*[@id="_container_baseInfo"]/table[2]/tbody/tr[2]/td[4]').text

            # 人员信息
            membersItemList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_staff"]/div/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_staff"]/div/table/tbody/tr'):
                    membersIem = dict()
                    if self.isElementExist(sel, './td[2]/div/a[1]'):
                        membersIem['memberName'] = sel.find_element_by_xpath('./td[2]/div/a[1]').text
                    if self.isElementExist(sel, './td[3]'):
                        membersIem['position'] = sel.find_element_by_xpath('./td[3]').text
                    membersItemList.append(membersIem)

            # 核心团队
            corememberList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_teamMember"]/div[1]/div'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_teamMember"]/div[1]/div'):
                    coremembersItem = dict()
                    if self.isElementExist(sel, './div[1]/div[2]'):
                        coremembersItem['memberName'] = sel.find_element_by_xpath('./div[1]/div[2]').text

                    if self.isElementExist(sel, './div[1]/div[1]/div[2]/img'):
                        coremembersItem['profilePhoto'] = sel.find_element_by_xpath(
                            './div[1]/div[1]/div[2]/img').get_attribute(
                            'data-src')
                    if self.isElementExist(sel, './div[2]/div'):
                        coremembersItem['position'] = sel.find_element_by_xpath('./div[2]/div').text
                    introduceList = []
                    if self.isElementExist(sel, './div[2]/p'):
                        introduceList.append(sel.find_element_by_xpath('./div[2]/p').text)
                    coremembersItem['introduce'] = ','.join(introduceList)
                    corememberList.append(coremembersItem)

            # 股东信息
            shareholderList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_holder"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_holder"]/table/tbody/tr'):
                    shareholderItem = dict()
                    if self.isElementExist(sel, './td[2]/div/div[2]/a'):
                        shareholderItem['shareholderName'] = sel.find_element_by_xpath('./td[2]/div/div[2]/a').text
                    if self.isElementExist(sel, './td[3]/div/div'):
                        shareholderItem['proportionCapital'] = sel.find_element_by_xpath('./td[3]/div/div').text
                    if self.isElementExist(sel, './td[4]/div'):
                        shareholderItem['subscribeCapital'] = sel.find_element_by_xpath('./td[4]/div').text

                    if self.isElementExist(sel, './td[5]/div'):
                        shareholderItem['proportionTime'] = sel.find_element_by_xpath('./td[5]/div').text
                    shareholderList.append(shareholderItem)

            # 融资历史
            financingList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_rongzi"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_rongzi"]/table/tbody/tr'):
                    financingItem = dict()

                    if self.isElementExist(sel, './td[2]'):
                        financingItem['time'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        financingItem['rotation'] = sel.find_element_by_xpath('./td[3]').text
                    if self.isElementExist(sel, './td[5]'):
                        financingItem['amountMoney'] = sel.find_element_by_xpath('./td[5]').text
                    if self.isElementExist(sel, './td[4]'):
                        financingItem['valuation'] = sel.find_element_by_xpath('./td[4]').text

                    if self.isElementExist(sel, './td[6]'):
                        financingItem['proportion'] = sel.find_element_by_xpath('./td[6]').text
                    if self.isElementExist(sel, './td[7]'):
                        financingItem['investor'] = sel.find_element_by_xpath('./td[7]').text

                    newsSource = dict()
                    if self.isElementExist(sel, './td[8]'):
                        newsSource['newsSource'] = sel.find_element_by_xpath('./td[8]').text
                    if self.isElementExist(sel, './td[8]'):
                        newsSource['url'] = sel.find_element_by_xpath('./td[8]').get_attribute('href')
                    financingItem['newsSource'] = newsSource

                    financingList.append(financingItem)

            # 投资事件
            investmentList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_touzi"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_touzi"]/table/tbody/tr'):
                    investmentItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        investmentItem['time'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        investmentItem['rotation'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[5]'):
                        investmentItem['amountMoney'] = sel.find_element_by_xpath('./td[5]').text
                    if self.isElementExist(sel, './td[7]'):
                        investmentItem['investor'] = sel.find_element_by_xpath('./td[7]').text

                    product = dict()
                    if self.isElementExist(sel, './td[6]/table/tbody/tr/td[2]/a'):
                        product['name'] = sel.find_element_by_xpath('./td[6]/table/tbody/tr/td[2]/a').text
                    if self.isElementExist(sel, './table/tbody/tr/td[1]/div[2]/img'):
                        product['url'] = sel.find_element_by_xpath('./table/tbody/tr/td[1]/div[2]/img').get_attribute(
                            'data-src')
                    investmentItem['product'] = product
                    if self.isElementExist(sel, './td[7]'):
                        investmentItem['region'] = sel.find_element_by_xpath('./td[7]').text

                    if self.isElementExist(sel, './td[8]/a'):
                        investmentItem['industry'] = sel.find_element_by_xpath('./td[8]/a').text
                    if self.isElementExist(sel, './td[9]'):
                        investmentItem['business'] = sel.find_element_by_xpath('./td[9]').text

                    investmentList.append(investmentItem)

            # 招聘信息
            recruitmentList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_recruit"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_recruit"]/table/tbody/tr'):
                    recruitmentItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        recruitmentItem['releaseTime'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        recruitmentItem['recruitmentPosition'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        recruitmentItem['salaryRange'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        recruitmentItem['workExperience'] = sel.find_element_by_xpath('./td[5]').text

                    if self.isElementExist(sel, './td[6]'):
                        recruitmentItem['recruitmentNum'] = sel.find_element_by_xpath('./td[6]').text
                    if self.isElementExist(sel, './td[7]'):
                        recruitmentItem['recruitmentCity'] = sel.find_element_by_xpath('./td[7]').text

                    recruitmentList.append(recruitmentItem)

            # 专利信息
            patentList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_patent"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_patent"]/table/tbody/tr'):
                    patentItem = dict()
                    if self.isElementExist(sel, './td[3]'):
                        patentItem['patentName'] = sel.find_element_by_xpath('./td[3]').text
                    if self.isElementExist(sel, './td[2]'):
                        patentItem['applicationDay'] = sel.find_element_by_xpath('./td[2]').text

                    if self.isElementExist(sel, './td[3]'):
                        patentItem['patentNum'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        patentItem['applicationNum'] = sel.find_element_by_xpath('./td[5]').text

                    if self.isElementExist(sel, './td[6]'):
                        patentItem['patentType'] = sel.find_element_by_xpath('./td[6]').text

                    patentList.append(patentItem)

            # 商标信息
            trademarkList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_tmInfo"]/div[2]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_tmInfo"]/div[2]/table/tbody/tr'):
                    trademarkItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        trademarkItem['trademarkTime'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]/div/div/img'):
                        trademarkItem['trademarkImage'] = sel.find_element_by_xpath(
                            './td[3]/div/div/img').get_attribute(
                            'data-src')

                    if self.isElementExist(sel, './td[4]'):
                        trademarkItem['trademarkName'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        trademarkItem['trademarkNum'] = sel.find_element_by_xpath('./td[5]').text

                    if self.isElementExist(sel, './td[6]'):
                        trademarkItem['trademarkType'] = sel.find_element_by_xpath('./td[6]').text
                    if self.isElementExist(sel, './td[7]'):
                        trademarkItem['trademarkProcess'] = sel.find_element_by_xpath('./td[7]').text

                    trademarkList.append(trademarkItem)

            # 软件著作权
            softwareList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_copyright"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_copyright"]/table/tbody/tr'):
                    softwareItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        softwareItem['softwareTime'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        softwareItem['softwareName'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        softwareItem['softwareProfile'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        softwareItem['softwareNum'] = sel.find_element_by_xpath('./td[5]').text

                    if self.isElementExist(sel, './td[6]'):
                        softwareItem['softwareTypeNum'] = sel.find_element_by_xpath('./td[6]').text
                    if self.isElementExist(sel, './td[7]'):
                        softwareItem['softwareVersion'] = sel.find_element_by_xpath('./td[7]').text

                    softwareList.append(softwareItem)

            # 作品著作权
            worksList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_copyrightWorks"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_copyrightWorks"]/table/tbody/tr'):
                    worksItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        worksItem['worksName'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        worksItem['worksNum'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        worksItem['worksType'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        worksItem['worksFinishedDate'] = sel.find_element_by_xpath('./td[5]').text

                    if self.isElementExist(sel, './td[6]'):
                        worksItem['worksRegisterDate'] = sel.find_element_by_xpath('./td[6]').text
                    if self.isElementExist(sel, './td[7]'):
                        worksItem['worksReleaseDate'] = sel.find_element_by_xpath('./td[7]').text

                    worksList.append(worksItem)

            # 网站备案
            webCheckList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_icp"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_icp"]/table/tbody/tr'):
                    webCheckItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        webCheckItem['webCheckDate'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        webCheckItem['webName'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        webCheckItem['webHomePage'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        webCheckItem['webDomain'] = sel.find_element_by_xpath('./td[5]').text

                    if self.isElementExist(sel, './td[6]'):
                        webCheckItem['webBackupsNum'] = sel.find_element_by_xpath('./td[6]').text
                    if self.isElementExist(sel, './td[7]'):
                        webCheckItem['webStatus'] = sel.find_element_by_xpath('./td[7]').text

                    if self.isElementExist(sel, './td[8]'):
                        webCheckItem['webProperties'] = sel.find_element_by_xpath('./td[8]').text

                    webCheckList.append(webCheckItem)

            # 开庭公告
            courtNoticeList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_pastAnnouncementCount"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_pastAnnouncementCount"]/table/tbody/tr'):
                    courtNoticeItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        courtNoticeItem['courtDate'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        courtNoticeItem['courtCase'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]/div'):
                        courtNoticeItem['courtPlaintiff'] = sel.find_element_by_xpath('./td[4]/div').text
                    if self.isElementExist(sel, './td[5]/div/a'):
                        courtNoticeItem['courtDefendant'] = sel.find_element_by_xpath('./td[5]/div/a').text

                    courtNoticeList.append(courtNoticeItem)

            #  法律诉讼
            legalList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_pastLawsuitCount"]/div/div[1]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath(
                        '//*[@id="_container_pastLawsuitCount"]/div/div[1]/table/tbody/tr'):
                    legalItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        legalItem['legalDate'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        legalItem['legalDocuments'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        legalItem['legalCase'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]/div'):
                        legalItem['legalIdentity'] = sel.find_element_by_xpath('./td[5]/div').text

                    if self.isElementExist(sel, './td[6]'):
                        legalItem['legalNum'] = sel.find_element_by_xpath('./td[6]').text

                    legalList.append(legalItem)

            # 法院公告
            courtAnnouncementList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_pastCourtCount"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_pastCourtCount"]/table/tbody/tr'):
                    courtAnnouncementItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        courtAnnouncementItem['courtDate'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        courtAnnouncementItem['courtPlaintiff'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        courtAnnouncementItem['courtDefendant'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        courtAnnouncementItem['courtType'] = sel.find_element_by_xpath('./td[5]').text

                    if self.isElementExist(sel, './td[6]'):
                        courtAnnouncementItem['courtName'] = sel.find_element_by_xpath('./td[6]').text

                    courtAnnouncementList.append(courtAnnouncementItem)

            # 失信人信息
            filingList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_dishonest"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_dishonest"]/table/tbody/tr'):
                    filingItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        filingItem['filingDate'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        filingItem['filingNum'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        filingItem['filingCourt'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        filingItem['performanceStatus'] = sel.find_element_by_xpath('./td[5]').text

                    if self.isElementExist(sel, './td[6]'):
                        filingItem['executionNum'] = sel.find_element_by_xpath('./td[6]').text

                    filingList.append(filingItem)
            # 被执行人
            executorList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_pastZhixing"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_pastZhixing"]/table/tbody/tr'):
                    executorItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        executorItem['filingDate'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        executorItem['filingExecutes'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        executorItem['filingNum'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        executorItem['filingCourt'] = sel.find_element_by_xpath('./td[5]').text

                    executorList.append(executorItem)

            # 司法协助
            judicialList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_judicialAid"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_judicialAid"]/table/tbody/tr'):
                    judicialItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        judicialItem['judicialExecutor'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        judicialItem['shareAmount'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        judicialItem['filingCourt'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        judicialItem['judicialNum'] = sel.find_element_by_xpath('./td[5]').text

                    if self.isElementExist(sel, './td[6]'):
                        judicialItem['judicialStatus'] = sel.find_element_by_xpath('./td[6]').text

                    judicialList.append(judicialItem)

            # 经营异常
            causeList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_abnormal"]/table/tbody/trw'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_abnormal"]/table/tbody/trw'):
                    causeItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        causeItem['causeDate'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        causeItem['causeReason'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        causeItem['determiningOrgan'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        causeItem['removalDate'] = sel.find_element_by_xpath('./td[5]').text

                    if self.isElementExist(sel, './td[6]'):
                        causeItem['removalReason'] = sel.find_element_by_xpath('./td[6]').text
                    if self.isElementExist(sel, './td[7]'):
                        causeItem['removalOrgan'] = sel.find_element_by_xpath('./td[7]').text

                    causeList.append(causeItem)

            # 行政处罚
            sanctionList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_punish"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_punish"]/table/tbody/tr'):
                    sanctionItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        sanctionItem['sanctionDate'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        sanctionItem['sanctionNum'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        sanctionItem['sanctionType'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        sanctionItem['sanctionOrgan'] = sel.find_element_by_xpath('./td[5]').text
                    sanctionList.append(sanctionItem)

            # 严重违法
            illegalityList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_illegal"]/table/tbody/tr[1]'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_illegal"]/table/tbody/tr[1]'):
                    illegalityItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        illegalityItem['illegalityDate'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        illegalityItem['illegalityReason'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        illegalityItem['illegalityOrgan'] = sel.find_element_by_xpath('./td[4]').text

                    illegalityList.append(illegalityItem)

            # 股权出质
            equityList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_pastEquityCount"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_pastEquityCount"]/table/tbody/tr'):
                    equityItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        equityItem['equityDate'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        equityItem['equityNum'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        equityItem['equityPledgor'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]/a'):
                        equityItem['equityPledgee'] = sel.find_element_by_xpath('./td[5]/a').text

                    if self.isElementExist(sel, './td[6]'):
                        equityItem['equityStatus'] = sel.find_element_by_xpath('./td[6]').text
                    equityList.append(equityItem)

            # 动产抵押
            mortgageList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_mortgage"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_mortgage"]/table/tbody/tr'):
                    mortgageItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        mortgageItem['mortgageDate'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        mortgageItem['mortgageNum'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        mortgageItem['mortgageType'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        mortgageItem['mortgageOrgan'] = sel.find_element_by_xpath('./td[5]').text

                    if self.isElementExist(sel, './td[6]'):
                        mortgageItem['mortgageStatus'] = sel.find_element_by_xpath('./td[6]').text

                    mortgageList.append(mortgageItem)

            # 欠税公告
            arrearsList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_towntax"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_towntax"]/table/tbody/tr'):
                    arrearsItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        arrearsItem['arrearsDate'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        arrearsItem['arrearsNum'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        arrearsItem['arrearsType'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        arrearsItem['arrearsBurden'] = sel.find_element_by_xpath('./td[5]').text

                    if self.isElementExist(sel, './td[6]'):
                        arrearsItem['arrearsBalance'] = sel.find_element_by_xpath('./td[6]').text
                    if self.isElementExist(sel, './td[7]'):
                        arrearsItem['arrearsOrgan'] = sel.find_element_by_xpath('./td[7]').text

                    arrearsList.append(arrearsItem)

            # 司法拍卖
            auctionList = []
            if self.isElementsExist(self.driver, '//*[@id="_container_judicialSale"]/table/tbody/tr'):
                for sel in self.driver.find_elements_by_xpath('//*[@id="_container_judicialSale"]/table/tbody/tr'):
                    auctionItem = dict()
                    if self.isElementExist(sel, './td[2]'):
                        auctionItem['auctionAnnouncement'] = sel.find_element_by_xpath('./td[2]').text
                    if self.isElementExist(sel, './td[3]'):
                        auctionItem['auctionDate'] = sel.find_element_by_xpath('./td[3]').text

                    if self.isElementExist(sel, './td[4]'):
                        auctionItem['auctionCourt'] = sel.find_element_by_xpath('./td[4]').text
                    if self.isElementExist(sel, './td[5]'):
                        auctionItem['auctionTarget'] = sel.find_element_by_xpath('./td[5]').text

                    auctionList.append(auctionItem)
            result = dict()
            # 基本信息
            result['baseinfo'] = item
            # 资本信息
            result['capital'] = capitalItem
            # 人员信息
            result['members'] = membersItemList
            # 核心团队
            result['coreteam'] = corememberList
            # 股东信息
            result['shareholder'] = shareholderList
            # 融资历史
            result['financing'] = financingList
            # 投资事件
            result['investment'] = investmentList
            # 招聘信息
            result['recruitment'] = recruitmentList
            # 专利信息
            result['patent'] = patentList
            # 商标信息
            result['trademark'] = trademarkList
            # 软件著作权
            result['software'] = softwareList
            # 作品著作权
            result['works'] = worksList
            # 网站备案
            result['webbackup'] = webCheckList
            # 开庭公告
            result['courtnotice'] = courtNoticeList
            #  法律诉讼
            result['legal'] = legalList
            # 法院公告
            result['courtannouncement'] = courtAnnouncementList
            # 失信人信息
            result['filing'] = filingList
            # 被执行人
            result['executor'] = executorList
            # 司法协助
            result['judicial'] = judicialList
            # 经营异常
            result['cause'] = causeList
            # 行政处罚
            result['sanction'] = sanctionList
            # 严重违法
            result['illegality'] = illegalityList
            # 股权出质
            result['equity'] = equityList
            # 动产抵押
            result['mortgage'] = mortgageList
            # 欠税公告
            result['arrears'] = arrearsList
            # 司法拍卖
            result['auction'] = auctionList
            # 企业业务
            result['business'] = business_list

            company_info = dict()
            company_info['name'] = name
            company_info['company_tianyancha'] = result
            self.logger.info(company_info)
            self.graceful_auto_reconnect(self.upsert)(company_info)
            self.graceful_auto_reconnect(self.update)(name)

        return []