#flask/bin/python
from flask import Flask, jsonify, request, abort, make_response, url_for, send_from_directory
from collections import Counter, OrderedDict
import re
import string
from urlparse import urlparse
import base64
from datetime import datetime as dt
from random import randint
from PIL import Image
import glob, os
import json
from ast import literal_eval
import traceback
import sys
from bs4 import BeautifulSoup
import urllib2
import redis
import MySQLdb
import celeryTask
from celery import Celery
from celery.result import AsyncResult
import sendgrid
from sendgrid.helpers.mail import *
from sets import Set

application = Flask(__name__)
application.config.update(CELERY_BROKER_URL = 'amqp://', CELERY_BACKEND='redis://localhost:6379')
celery = celeryTask.make_celery(application)

def orderer(counted, minLen):
    wordList = []
    ordered = OrderedDict(sorted(counted.items(), key=lambda x: (-x[1], x[0])))
    for item in ordered.items():
        if len(item[0]) >= int(minLen):
            wordList.append(item)
    return wordList

def article_processor(article, ignoreNum=0, minLen=0):
    article = article.encode("utf-8")
    #sanitized = article.translate(None, string.punctuation).lower().split()
    sanitized = str(article.translate(string.maketrans(string.punctuation,' '*len(string.punctuation)))).lower().split()
    occur = Counter(reversed(sorted(sanitized)))
    uniques = len(occur.keys())
    print sanitized
    if ignoreNum != 0:
        # Below code is inspired by http://stackoverflow.com/questions/3159155/how-to-remove-all-integer-values-from-a-list-in-python
        numSanitized = [x for x in sanitized if not (x.isdigit() or x[0] == '-' and x[1:].isdigit())]
        occur = Counter(reversed(sorted(numSanitized)))
    return (uniques, orderer(occur, minLen), sanitized)

def lastlineReader(fname, n):
    stdin, stdout = os.popen2("tail -n " + str(n) + " " + fname)
    stdin.close()
    lines = stdout.readlines()
    stdout.close()
    return lines

@celery.task(bind=True)
def resizer(self, uploadTime, hostname, dm, em, imgString):
    try:
        path = "./static/images/"
        randomNum = ''.join(["%s" % randint(0,9) for num in range(0,5)])
        extension = ".jpg"
        thumbExt = ".tn.jpg"
        resizeExt = ".rs.jpg"
        fullname = path + uploadTime + randomNum + extension

        imgOrigin = open(fullname, "w+")
        imgOrigin.write(base64.decodestring(imgString))
        imgOrigin.seek(0)

        RsImg = Image.open(imgOrigin).copy()
        TnImg = Image.open(imgOrigin).copy()
        if TnImg.size[0] > TnImg.size[1]:
            imgRatio = TnImg.size[1] / float(TnImg.size[0])
            RsImg = RsImg.resize((dm, int(dm*imgRatio)), Image.LANCZOS)
            TnImg.thumbnail((TnImg.size[0], 64), Image.LANCZOS)
            TnImg = TnImg.crop(((TnImg.size[0]/2)-32, 0, (TnImg.size[0]/2)+32, 64))
        else:
            imgRatio = TnImg.size[0] / float(TnImg.size[1])
            RsImg = RsImg.resize((int(dm*imgRatio), dm), Imgae.LANCZOS)
            TnImg.thumbnail((64, TnImg.size[1]), Image.LANCZOS)
            TnImg = TnImg.crop((0, (TnImg.size[1]/2)-32, 64, (TnImg.size[1]/2)+32))
        RsImg.save(path + uploadTime + randomNum + resizeExt, "JPEG")
        TnImg.save(path + uploadTime + randomNum + thumbExt, "JPEG")
        imgOrigin.close()

        imgUrl = "http://" + hostname + "/images/" + uploadTime + randomNum + extension
        rsUrl = "http://" + hostname + "/images/" + uploadTime + randomNum + resizeExt
        thumbnailUrl = "http://" + hostname + "/images/" + uploadTime + randomNum + thumbExt
        
        sg = sendgrid.SendGridAPIClient(apikey='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')
        from_email = Email("kalihman0515@link.cuhk.edu.hk")
        subject = "Image resize email"
        to_email = Email(str(em))
        content = Content("text/plain", rsUrl + "\n" + thumbnailUrl)
        mail = Mail(from_email, subject, to_email, content)
        response = sg.client.mail.send.post(request_body=mail.get())
        print(response.status_code)
        print(response.body)
        print(response.headers)
    
    except Exception, e:
        print e


@application.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Resource Not found'}), 404)

@application.route('/')
def home():
    path = '/static/'
    return send_from_directory('static', 'index.html')

@application.route('/assets/<path:path>')
def assets(path):
    return send_from_directory('static/assets', path)

@application.route('/app/submit_article', methods=['GET', 'POST'])
def process_article():
    article =  request.values.get('article')
    igNum =  request.values.get('ignore_numbers')
    minLen =  request.values.get('min_length')
    port = urlparse(request.url_root).port
    processed = ()
    if article:
        if article == "":
            return jsonify({'status': "success", 'port': str(port), 'unique_words': 0, 'words': []})
        if igNum and minLen:
            processed = article_processor(article, igNum, minLen)
        elif igNum:
            processed = article_processor(article, igNum)
        elif minLen:
            processed = article_processor(article, 0, minLen)
        else:
            processed = article_processor(article)
        return jsonify({'status': "success", 'port': str(port), 'header': str(request.headers), 'unique_words': processed[0], 'words': processed[1]})
    else:
        return jsonify({'status': "failed", 'reason': "Article parameter not given"})

@application.route('/app/submit_image', methods=['POST'])
def process_image():
    try:
        exc_info = sys.exc_info()
        hostName = str(request.headers.get("Server-Name"))
        port = urlparse(request.url_root).port
        imageString = request.values.get('image')
        
        path = "./static/images/"
        uploadTime = dt.utcnow().strftime("%Y%m%d-%H%M%S-")
        randomNum = ''.join(["%s" % randint(0,9) for num in range(0,5)])
        extension = ".jpg"
        thumbExt = ".tn.jpg"
        fullname = path + uploadTime + randomNum + extension
        
        img = open(fullname, "w+")
        img.write(base64.decodestring(imageString))
        img.seek(0)

        pilImg = Image.open(img).copy()
        if pilImg.size[0] > pilImg.size[1]:
            pilImg.thumbnail((pilImg.size[0], 64), Image.LANCZOS)
            pilImg = pilImg.crop(((pilImg.size[0]/2)-32, 0, (pilImg.size[0]/2)+32, 64))
        else:
            pilImg.thumbnail((64, pilImg.size[1]), Image.LANCZOS)
            pilImg = pilImg.crop((0, (pilImg.size[1]/2)-32, 64, (pilImg.size[1]/2)+32))
        pilImg.save(path + uploadTime +randomNum + thumbExt, "JPEG")
        img.close()
                
        imgUrl = "http://" + hostName + "/images/" + uploadTime + randomNum + extension
        thumbnailUrl = "http://" + hostName + "/images/" + uploadTime + randomNum + thumbExt
        recentList = [literal_eval(f) for f in lastlineReader("upload_log", 3)]
        recentListFile = open("upload_log", 'a')
        recentListFile.write("{'image_url': '" + imgUrl + "', 'image_thumbnail_url': '" + thumbnailUrl + "'}\n")
        recentListFile.close()
        
        return jsonify({"status":"success", "port": str(port), "image_url": imgUrl, "image_thumbnail_url": thumbnailUrl, "recent_uploads": recentList})
    except Exception, e:
        traceback.print_exception(*exc_info)
        x = traceback.format_exc()
        return jsonify({"status": "failed", "Error": str(x)})

@application.route('/app/submit_url', methods=['POST'])
def process_url():
    R_SERV = redis.Redis("localhost")
    M_SERV = MySQLdb.connect(user="root", passwd="persistentYJ92!", db="ierg4080")
    try:
        ### 1. Extract title and description from URL
        submit_time = dt.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        url = request.values.get('url').encode('utf-8').strip()
        if(R_SERV.get(url)):
            parsed = json.loads(R_SERV.get(url))
            parsed['from_cache'] = 1
            return make_response(jsonify(parsed))
        else:
            soup = BeautifulSoup(urllib2.urlopen(url).read(), 'html.parser')
            title = soup.title.string.encode('utf-8').strip()
            description = ""
            for meta in soup.findAll("meta"):
                metaname = meta.get('name', '').lower()
                metaprop = meta.get('property', '').lower()
                if 'description' == metaname or metaprop.find("description")>0:
                    description = meta['content'].encode('utf-8').strip()
            cur = M_SERV.cursor()
            cur.execute("INSERT INTO urls (url, title, description, submited_at) VALUES (%s, %s, %s, %s)", (url, title, description, submit_time))
            #print title
            uniqueList = article_processor(title)[2]
            cur.execute("SELECT id FROM urls WHERE url = %s", (url,))
            urlID = str(cur.fetchone()[0])
            #print uniqueList
            #print urlID
            for kw in uniqueList:
                cur.execute("INSERT INTO title_index (keyword, url_id) VALUES (%s, %s)",(kw, urlID, ))
            M_SERV.commit()
            res = {"status": "success", "result":{"url": url, "title": title, "description": description},"from_cache": 0}
            R_SERV.set(url, json.dumps(res))
            return make_response(jsonify(res))
    except M_SERV.Error, e:
        if M_SERV:
            M_SERV.rollback()
            M_SERV.close()
        return jsonify({"status": "failed", "Error": str(traceback.format_exc(e))})
    except Exception, e:
        return jsonify({"status": "failed", "Error": str(traceback.format_exc(e))})

@application.route('/app/list_urls', methods=['GET'])
def listing_urls():
    M_SERV = MySQLdb.connect(user="root", passwd="persistentYJ92!", db="ierg4080")
    try:
        cur = M_SERV.cursor()
        cur.execute("SELECT * from urls ORDER BY submited_at DESC LIMIT 5")
        data = cur.fetchall()
        jsonList = []
        for t in data:
            jsonList.append(dict(urls=t[1], title=t[2], description=t[3], submitted_at=t[4].strftime("%Y-%m-%d %H:%M:%S")))
        return jsonify({"status": "success", "urls": jsonList})
    except Exception, e:
        return jsonify({"status": "failed", "Error": str(traceback.format_exc(e))})
    finally:
        if M_SERV:
            M_SERV.close() 

@application.route('/app/search_url_title', methods=['POST'])
def search_url():
    M_SERV = MySQLdb.connect(user="root", passwd="persistentYJ92!", db="ierg4080")
    try:
        kw = request.values.get('keyword').encode('utf-8').lower().strip()
        print kw
        cur = M_SERV.cursor()
        cur.execute("SELECT DISTINCT urls.url, urls.title, urls.submited_at FROM urls JOIN title_index ON title_index.keyword = %s AND urls.id = title_index.url_id ORDER BY urls.submited_at DESC", (kw,))
        data = cur.fetchall()
        jsonList = []
        for t in data:
            jsonList.append(dict(urls=t[0], title=t[1], submitted_at=t[2].strftime("%Y-%m-%d %H:%M:%S")))
        return jsonify({"status": "success", "urls": jsonList}) 
    except Exception, e:
        return jsonify({"status": "failed", "Error": str(traceback.format_exc(e))})
    finally:
        if M_SERV:
            M_SERV.close()

@application.route('/app/resize_image', methods=['POST'])
def resize_image():
    try:
        uploadTime = dt.utcnow().strftime("%Y%m%d-%H%M%S-")
        dm = int(request.values.get("dimension"))
        em = request.values.get("email")
        hostName = str(request.headers.get("Server-Name"))
        imageString = request.values.get("image")
        resize_task = resizer.apply_async((uploadTime, hostName, dm, em, imageString))
        #hostName = str(request.headers.get("Server-Name"))
        #port = urlparse(request.url_root).port
        #imageString = request.values.get('image')
        return jsonify({ "status": "success", "task_id": str(resize_task.task_id) })
    except Exception, e:
        return jsonify({"status": "failed", "Error": str(traceback.format_exc(e))})

@application.route('/app/check_resize_status', methods=['POST'])
def task_query():
    try:
        taskId = request.values.get("task_id")
        res = resizer.AsyncResult(taskId)
        if str(res.state) in Set(["SUCCESS", "FAILURE"]):
            return jsonify({"status": "success", "resize_status": "finished"})
        else:
            return jsonify({"status": "success", "resize_status": "in progress"})
    except Exception, e:
        return jsonify({"status": "failed", "Error": str(traceback.format_exc)})

@application.route('/app/scanner', methods=['POST', 'GET'])
def scanner_handler():
    if request.method == 'POST':
        M_SERV = MySQLdb.connect(user="root", passwd="persistentYJ92!", db="seem4680")
        try:
        ### 1. Extract values from request
        # Expected values: 'distance', 'namespace', 'txPower', 'instance', 'lastSeen', 'rssi', 'type'
        #submit_time = dt.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        #url = request.values.get('url').encode('utf-8').strip()
            content = request.get_json()
            namespace = content['namespace']
            instance = content['instance']
            lastSeen = content['lastSeen']
            txPower = content['txPower']
            status = content['status']
            station = content['station']
            beaconId = content['id']
            lastSeenDT = dt.fromtimestamp(lastSeen/1000).strftime("%Y-%m-%d %H:%M:%S")       
         
            cur = M_SERV.cursor()
            cur.execute("INSERT INTO scan_record (namespace, beaconId, instance, txPower, lastSeen, status, station) VALUES (%s, %s, %s, %s, %s, %s, %s)", [namespace, beaconId, instance, txPower, lastSeenDT, status, station])
            M_SERV.commit()
            return jsonify({ "received": str(request.get_json()) })
        except M_SERV.Error, e:
            if M_SERV:
                M_SERV.rollback()
                M_SERV.close()
        
            return jsonify({"status": "received"})
        except Exception, e:
            return jsonify({"status": "failed", "Error": str(traceback.format_exc(e))}) 
    else:
        M_SERV = MySQLdb.connect(user="root", passwd="persistentYJ92!", db="seem4680")
        try:
            jsonList = []
            cur = M_SERV.cursor()
            '''
            cur.execute("SELECT DISTINCT beaconID FROM scan_record")
            beaconlist = cur.fetchall()
            for b in beaconlist:
                cur.execute("SELECT status, (UNIX_TIMESTAMP(lastSeen)), beaconID, station FROM scan_record WHERE beaconID = %s ORDER BY lastSeen DESC LIMIT 2", [b])    
                #cur.execute("SELECT status, (UNIX_TIMESTAMP(lastSeen)), beaconID, station FROM scan_record WHERE id IN (SELECT MAX(id) FROM scan_record GROUP BY beaconID)")
                data = cur.fetchall()
                for t in data:
                    jsonList.append(dict(station=t[3], beaconID=t[2], timestamp=str(t[1]), status=t[0]))
            '''
            cur.execute("SELECT status, (UNIX_TIMESTAMP(lastSeen)), beaconID, station FROM scan_record WHERE id IN (SELECT MAX(id) FROM scan_record GROUP BY beaconID)")
            data  = cur.fetchall()
            for t in data:
                jsonList.append(dict(station=t[3], beaconID=t[2], timestamp=str(t[1]), status=t[0]))
            M_SERV.close()
            return jsonify(jsonList) 
        except Exception, e:
            return jsonify({"status": "failed", "Error": str(traceback.format_exc(e))}) 


if __name__=="__main__":
    application.run(host='0.0.0.0')
