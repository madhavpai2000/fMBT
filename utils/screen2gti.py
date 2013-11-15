#!/usr/bin/env python

# fMBT, free Model Based Testing tool
# Copyright (c) 2013, Intel Corporation.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms and conditions of the GNU Lesser General Public License,
# version 2.1, as published by the Free Software Foundation.
#
# This program is distributed in the hope it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for
# more details.
#
# You should have received a copy of the GNU Lesser General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin St - Fifth Floor, Boston, MA 02110-1301 USA.
#
# This is a small tool for converting UI events into fmbtgti interface
# method calls.

from PySide import QtCore
from PySide import QtGui

import getopt
import fmbtgti
import math
import os
import re
import shutil
import sys
import time
import traceback

def error(msg, exitStatus=1):
    sys.stderr.write("screen2gti: %s\n" % (msg,))
    sys.exit(1)

def debug(msg, debugLevel=1):
    if opt_debug >= debugLevel:
        sys.stderr.write("screen2gti debug: %s\n" % (msg,))

def log(msg):
    sys.stdout.write("%s\n" % (msg,))
    sys.stdout.flush()

_g_importFmbtRE = re.compile("\s*import fmbt(android|tizen|vnc|x11)")
_g_gtiInstantiateRE = re.compile("(([a-zA-Z_][a-zA-Z_0-9]*)\s*=\s*fmbt(android|tizen|vnc|x11)\.(Device|Screen)\s*\(.*\))")

########################################################################
# Convert events to fmbtgti API calls

class GestureEvent(object):
    __slots__ = ["time", "event", "key", "pos"]
    def __init__(self, event, key, pos):
        self.time = time.time()
        self.event = event
        self.key = key
        self.pos = pos
    def __str__(self):
        return 'GestureEvent(time=%s, event="%s", key=%s, pos=%s)' % (
            self.time, self.event, self.key, self.pos)

def quantify(item, quantum):
    if not isinstance(item, tuple) and not isinstance(item, list):
        return int(item * (1/quantum)) * quantum
    else:
        return tuple([int(i * (1/quantum)) * quantum for i in item])

def gestureToGti(gestureEventList):
    timeQuantum = 0.1 # seconds
    locQuantum = 0.01 # 1.0 = full display height/width
    distQuantum = 0.1  # 1.0 = full dist from point to edge

    quantL = lambda v: quantify(v, locQuantum)
    quantT = lambda v: quantify(v, timeQuantum)

    el = gestureEventList

    firstEvent = el[0].event
    lastEvent = el[-1].event
    duration = el[-1].time - el[0].time
    distance = 0
    xDistance = 0
    yDistance = 0
    lastX, lastY = el[0].pos
    for e in el[1:]:
        xDistance += abs(lastX - e.pos[0])
        yDistance += abs(lastY - e.pos[1])
        distance += math.sqrt((lastX - e.pos[0])**2 +
                              (lastY - e.pos[1])**2)
        lastX, lastY = e.pos

    if firstEvent == "mousedown" and lastEvent == "mouseup":
        between_events = set([e.event for e in el[1:-1]])
        if between_events in (set(), set(["mousemove"])):
            # event sequence: mousedown, mousemove..., mouseup
            if duration < 3 * timeQuantum:
                # very quick event, make it single tap
                return ".tap((%s, %s))" % quantL(el[0].pos)
            elif distance < 3 * locQuantum:
                # neglible move, make it long tap
                return ".tap((%s, %s), hold=%s)" % (
                    quantL(el[0].pos) + quantT([duration]))
            elif xDistance < 3 * locQuantum:
                if el[-1].pos[1] < el[0].pos[1]:
                    direction = "north"
                    sdist = yDistance + (1-el[0].pos[1])
                else:
                    direction = "south"
                    sdist = yDistance + el[0].pos[1]
                # only y axis changed, we've got a swipe
                return '.swipe((%s, %s), "%s", distance=%s)' % (
                    quantL(el[0].pos) + (direction,) +
                    quantL([sdist]))
            elif yDistance < 3 * locQuantum:
                if el[-1].pos[0] < el[0].pos[0]:
                    direction = "west"
                    sdist = xDistance + (1-el[0].pos[0])
                else:
                    direction = "east"
                    sdist = xDistance + el[0].pos[0]
                # only y axis changed, we've got a swipe
                return '.swipe((%s, %s), "%s", distance=%s)' % (
                    quantL(el[0].pos) + (direction,) +
                    quantL([sdist]))
            else:
                return ".drag(%s, %s)" % (quantL(el[0].pos), quantL(el[-1].pos))
        else:
            return "unknown between events"
    else:
        return "unknown gesture"

########################################################################
# GUI

class MyScaleEvents(QtCore.QObject):
    """
    Catch scaling events: Ctrl++, Ctrl+-, Ctrl+wheel. Change
    attrowner's attribute "wheel_scale" accordingly. Finally call
    attrowner's wheel_scale_changed().
    """
    def __init__(self, mainwindow, attrowner, min_scale, max_scale):
        QtCore.QObject.__init__(self, mainwindow)
        self.min_scale  = min_scale
        self.max_scale  = max_scale
        self.attrowner  = attrowner
        self.mainwindow = mainwindow
        self.visibleTip = None
        self.selTop, self.selLeft = None, None
    def changeScale(self, coefficient):
        self.attrowner.wheel_scale *= coefficient
        if self.attrowner.wheel_scale < self.min_scale: self.attrowner.wheel_scale = self.min_scale
        elif self.attrowner.wheel_scale > self.max_scale: self.attrowner.wheel_scale = self.max_scale
        self.attrowner.wheel_scale_changed()
    def eventFilter(self, obj, event):
        if self.mainwindow._selectingBitmap:
            return self.eventToSelect(event)
        else:
            return self.eventToAPI(event)
    def eventToSelect(self, event):
        w = self.mainwindow
        if event.type() == QtCore.QEvent.MouseButtonPress:
            self.selLeft, self.selTop = self.posToAbs(event.pos)
        elif event.type() == QtCore.QEvent.MouseMove:
            if self.selTop != None:
                right, bottom = self.posToAbs(event.pos)
                w.drawRect(self.selLeft, self.selTop, right, bottom)
        elif event.type() == QtCore.QEvent.MouseButtonRelease:
            if self.selTop != None:
                right, bottom = self.posToAbs(event.pos)
                w.selectBitmapDone(self.selLeft, self.selTop, right, bottom)
                self.selTop, self.selLeft = None, None
        return False
    def posToRel(self, pos):
        sbY = self.attrowner.verticalScrollBar().value()
        sbX = self.attrowner.horizontalScrollBar().value()
        wS = self.attrowner.wheel_scale
        x = (pos().x() + sbX) / wS / float(self.mainwindow.screenshotImage.width())
        y = (pos().y() + sbY) / wS / float(self.mainwindow.screenshotImage.height())
        return (x, y)
    def posToAbs(self, pos):
        sbY = self.attrowner.verticalScrollBar().value()
        sbX = self.attrowner.horizontalScrollBar().value()
        wS = self.attrowner.wheel_scale
        x = (pos().x() + sbX) / wS
        y = (pos().y() + sbY) / wS
        return (x, y)
    def eventToAPI(self, event):
        if event.type() == QtCore.QEvent.MouseMove:
            if self.mainwindow.gestureStarted:
                self.mainwindow.gestureEvents.append(
                    GestureEvent("mousemove", None, self.posToRel(event.pos)))
        elif event.type() == QtCore.QEvent.MouseButtonPress:
            if not self.mainwindow.gestureStarted:
                self.mainwindow.gestureStarted = True
                self.mainwindow.gestureEvents = [
                    GestureEvent("mousedown", 0, self.posToRel(event.pos))]
        elif event.type() == QtCore.QEvent.MouseButtonRelease:
            if self.mainwindow.gestureStarted:
                self.mainwindow.gestureStarted = False
                self.mainwindow.gestureEvents.append(
                    GestureEvent("mouseup", 0, self.posToRel(event.pos)))
                s = gestureToGti(self.mainwindow.gestureEvents)
                cmd = self.mainwindow._sut + s
                self.mainwindow.gestureEvents = []
                if self.mainwindow.screenshotButtonControl.isChecked():
                    debug("sending command %s" % (cmd,))
                    self.mainwindow.runStatement(cmd, autoUpdate=True)
                else:
                    debug("dropping command %s" % (cmd,))
                if self.mainwindow.editorButtonRec.isChecked():
                    self.mainwindow.editor.insertPlainText(cmd + "\n")
        elif event.type() == QtCore.QEvent.ToolTip:
            if not hasattr(self.attrowner, 'cursorForPosition'):
                return False
            filename = self.mainwindow.bitmapStringAt(event.pos())
            if filename == None:
                QtGui.QToolTip.hideText()
                self.visibleTip = None
            else:
                filepath = self.mainwindow.bitmapFilepath(filename)
                if filepath:
                    if self.visibleTip != filepath:
                        QtGui.QToolTip.hideText()
                        txt = '%s<br><img src="%s">' % (filepath, filepath)
                        fsfilepath = filepath + ".fullscreen.png"
                        if os.access(fsfilepath, os.R_OK):
                            txt += '<br><img width="240" src="%s">' % (fsfilepath,)
                        else:
                            print "no access to"
                            print fsfilepath
                        QtGui.QToolTip.showText(event.globalPos(), txt)
                else:
                    QtGui.QToolTip.showText(event.globalPos(), '%s<br>not in bitmapPath' % (filename,))
                self.visibleTip = filepath
            return True

        if event.type() == QtCore.QEvent.Wheel and event.modifiers() == QtCore.Qt.ControlModifier:
            coefficient = 1.0 + event.delta() / 1440.0
            self.changeScale(coefficient)
        return False

class fmbtdummy(object):
    class Device(fmbtgti.GUITestInterface):
        def __init__(self, screenshotList=[]):
            fmbtgti.GUITestInterface.__init__(self)
            self._paths = fmbtgti._Paths(
                os.getenv("FMBT_BITMAPPATH",""),
                os.getenv("FMBT_BITMAPPATH_RELROOT", ""))
            self.setConnection(
                fmbtdummy.Connection(screenshotList))
    class Connection(fmbtgti.GUITestConnection):
        def __init__(self, screenshotList):
            fmbtgti.GUITestConnection.__init__(self)
            self.scl = screenshotList
        def recvScreenshot(self, filename):
            scr = self.scl[0]
            self.scl.append(self.scl.pop(0))
            shutil.copyfile(scr, filename)
            return True
        def sendTap(self, x, y):
            return True
        def sendTouchDown(self, x, y):
            return True
        def sendTouchMove(self, x, y):
            return True
        def sendTouchUp(self, x, y):
            return True

class MainWindow(QtGui.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)

        self._autoConnectGti = None
        self._autoConnectModules = None
        self._bitmapSaveDir = os.getcwd()
        self._fmbtEnv = {}
        self._bitmapFileFormats = ["Portable network graphics (*.png)", "All files (*.*)"]
        self._scriptFileFormats = ["Python scripts (*.py)", "All files (*.*)"]
        self._scriptFilename = None
        self._selectingBitmap = None
        self._sut = None

        self.mainwidget = QtGui.QWidget()
        self.layout = QtGui.QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.mainwidget.setLayout(self.layout)

        self.splitter = QtGui.QSplitter(self.mainwidget)
        self.layout.addWidget(self.splitter, 1)

        ### Screenshot widgets
        self.screenshotWidgets = QtGui.QWidget(self.mainwidget)
        self.screenshotWidgets.setContentsMargins(0, 0, 0, 0)
        self.screenshotWidgetsLayout = QtGui.QVBoxLayout()
        self.screenshotWidgets.setLayout(self.screenshotWidgetsLayout)

        self.screenshotButtons = QtGui.QWidget(self.screenshotWidgets)
        self.screenshotButtonsL = QtGui.QHBoxLayout()
        self.screenshotButtons.setLayout(self.screenshotButtonsL)
        self.screenshotButtonRefresh = QtGui.QPushButton(self.screenshotButtons,
                                                         text="&Refresh",
                                                         checkable = True)
        self.screenshotButtonRefresh.clicked.connect(self.updateScreenshot)
        self.screenshotButtonsL.addWidget(self.screenshotButtonRefresh)
        self.screenshotButtonControl = QtGui.QPushButton(self.screenshotButtons,
                                                        text="C&ontrol",
                                                        checkable = True)
        self.screenshotButtonControl.clicked.connect(self.controlDevice)
        self.screenshotButtonsL.addWidget(self.screenshotButtonControl)
        self.screenshotButtonSelect = QtGui.QPushButton(self.screenshotButtons,
                                                         text="Select",
                                                         checkable = True)
        self.screenshotButtonSelect.clicked.connect(self.selectBitmap)
        self.screenshotButtonsL.addWidget(self.screenshotButtonSelect)
        self.screenshotWidgetsLayout.addWidget(self.screenshotButtons)

        def makeScalableImage(parent, qlabel):
            container = QtGui.QWidget(parent)
            container.setContentsMargins(0, -8, 0, -8)
            layout = QtGui.QHBoxLayout()
            container.setLayout(layout)

            qlabel.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Ignored)
            qlabel.setScaledContents(True)
            qlabel.resize(QtCore.QSize(0,0))

            area = QtGui.QScrollArea(container)
            area.setContentsMargins(0, 0, 0, 0)
            area.setWidget(qlabel)
            qlabel._scaleevents = MyScaleEvents(self, area, 0.1, 1.0)
            area.wheel_scale = 1.0
            area.wheel_scale_changed = lambda: qlabel.resize(area.wheel_scale * qlabel.pixmap().size())
            area.installEventFilter(qlabel._scaleevents)
            layout.addWidget(area)
            container.area = area
            container._layout = layout # protect from garbage collector
            return container

        self.screenshotQLabel = QtGui.QLabel(self.screenshotWidgets)
        self.screenshotQLabel.setContentsMargins(0, 0, 0, 0)
        self.screenshotContainer = makeScalableImage(self.screenshotWidgets, self.screenshotQLabel)
        self.screenshotWidgetsLayout.addWidget(self.screenshotContainer)
        self.screenshotImage = QtGui.QImage()

        self.screenshotQLabel.setPixmap(
            QtGui.QPixmap.fromImage(
                self.screenshotImage))

        self.splitter.addWidget(self.screenshotWidgets)

        ### Editor widgets
        self.editorWidgets = QtGui.QWidget(self.mainwidget)
        self.editorWidgets.setContentsMargins(0, 0, 0, 0)
        self.editorWidgetsLayout = QtGui.QVBoxLayout()
        self.editorWidgets.setLayout(self.editorWidgetsLayout)

        self.editorButtons = QtGui.QWidget(self.editorWidgets)
        self.editorButtons.setContentsMargins(-5, 0, -5, 0)
        self.editorButtonsLayout = QtGui.QHBoxLayout()
        self.editorButtons.setLayout(self.editorButtonsLayout)

        self.editorButtonRec = QtGui.QPushButton("Re&c", checkable=True)
        self.editorButtonRec.clicked.connect(self.rec)
        self.editorButtonRunSingle = QtGui.QPushButton("Run &line")
        self.editorButtonRunSingle.clicked.connect(self.runSingleLine)
        self.editorButtonRunSingleUpdate = QtGui.QPushButton("Run + &update")
        self.editorButtonRunSingleUpdate.clicked.connect(lambda: self.runSingleLine(autoUpdate=True))
        self.editorButtonsLayout.addWidget(self.editorButtonRec)
        self.editorButtonsLayout.addWidget(self.editorButtonRunSingle)
        self.editorButtonsLayout.addWidget(self.editorButtonRunSingleUpdate)
        self.editorWidgetsLayout.addWidget(self.editorButtons)

        def makeScalableEditor(parent, font, EditorClass = QtGui.QTextEdit):
            editor = EditorClass()
            editor.setUndoRedoEnabled(True)
            editor.setLineWrapMode(editor.NoWrap)
            editor.setFont(font)
            editor._scaleevents = MyScaleEvents(self, editor, 0.1, 2.0)
            editor.wheel_scale = 1.0
            editor.wheel_scale_changed = lambda: (font.setPointSize(editor.wheel_scale * 12.0), editor.setFont(font))
            editor.installEventFilter(editor._scaleevents)
            return editor

        self.editorFont = QtGui.QFont()
        self.editorFont.setFamily('Courier')
        self.editorFont.setFixedPitch(True)
        self.editorFont.setPointSize(12)
        self.editor = makeScalableEditor(self.mainwidget, self.editorFont)
        self.editorWidgetsLayout.addWidget(self.editor)
        self.editor.cursorPositionChanged.connect(self.editorCursorPositionChanged)

        self.splitter.addWidget(self.editorWidgets)

        self.setCentralWidget(self.mainwidget)

        ### Menus
        fileMenu = QtGui.QMenu("&File", self)
        self.menuBar().addMenu(fileMenu)
        fileMenu.addAction("New An&droid", self.newAndroid)
        fileMenu.addAction("New &Tizen", self.newTizen)
        fileMenu.addAction("New &VNC", self.newVNC)
        fileMenu.addAction("New &X11", self.newX11)
        fileMenu.addAction("&Open", self.open, "Ctrl+O")
        fileMenu.addSeparator()
        fileMenu.addAction("&Save", self.save, "Ctrl+S")
        fileMenu.addAction("Save &As", self.saveAs, "Shift+Ctrl+S")
        fileMenu.addSeparator()
        fileMenu.addAction("E&xit", QtGui.qApp.quit, "Ctrl+Q")

        viewMenu = QtGui.QMenu("&View", self)
        self.menuBar().addMenu(viewMenu)
        viewMenu.addAction("Refresh screenshot", self.updateScreenshot, "Ctrl+R")
        viewMenu.addAction("Zoom in editor", self.zoomInEditor, "Ctrl++")
        viewMenu.addAction("Zoom out editor", self.zoomOutEditor, "Ctrl+-")
        viewMenu.addAction("Zoom in screenshot", self.zoomInScreenshot, "Ctrl+.")
        viewMenu.addAction("Zoom out screenshot", self.zoomOutScreenshot, "Ctrl+,")

        bitmapMenu = QtGui.QMenu("&Bitmap", self)
        self.menuBar().addMenu(bitmapMenu)
        bitmapMenu.addAction("Se&lect", self.selectBitmap, "Ctrl+B, Ctrl+L")
        bitmapMenu.addSeparator()
        bitmapMenu.addAction("&Swipe", self.swipeBitmap, "Ctrl+B, Ctrl+S")
        bitmapMenu.addAction("&Tap", self.tapBitmap, "Ctrl+B, Ctrl+T")
        bitmapMenu.addAction("&Verify", self.verifyBitmap, "Ctrl+B, Ctrl+V")

        self.gestureEvents = []
        self.gestureStarted = False

    def bitmapStringAt(self, pos=None):
        filename = None
        if pos != None:
            cursor = self.editor.cursorForPosition(pos)
        else:
            cursor = self.editor.textCursor()
        pos = cursor.positionInBlock()
        lineno = cursor.blockNumber()
        cursor.select(QtGui.QTextCursor.LineUnderCursor)
        l = cursor.selectedText()
        start = l.rfind('"', 0, pos-1)
        end = l.find('"', pos-1)
        if -1 < start < end:
            quotedString = l[start+1:end]
            if quotedString.lower().rsplit(".")[-1] in ["png", "jpg"]:
                filename = quotedString
        return filename

    def bitmapFilepath(self, filename):
        try:
            filepath, exc = self._fmbtEval(
                '%s._paths.abspath("%s")' % (self._sut, filename))
            return filepath
        except ValueError:
            return None

    def invalidateScreenshot(self):
        self.screenshotButtonRefresh.setChecked(True)
        self.screenshotButtonRefresh.repaint()
        _app.processEvents()

    def scheduleUpdateScreenshot(self, seconds):
        QtCore.QTimer.singleShot(int(seconds * 1000), self.updateScreenshot)

    def rec(self):
        self.editor.setFocus()

    def runSingleLine(self, lineNumber=None, autoUpdate=False):
        if lineNumber == None:
            line = self.editor.textCursor().block().text().strip()
            if line == "" or line.startswith("#"):
                self.editor.moveCursor(QtGui.QTextCursor.Down, QtGui.QTextCursor.MoveAnchor)
            elif self.runStatement(line):
                self.editor.moveCursor(QtGui.QTextCursor.Down, QtGui.QTextCursor.MoveAnchor)
                self.scheduleUpdateScreenshot(1.0)
            self.editor.setFocus()
        else:
            raise NotImplementedError

    def runStatement(self, statement, autoUpdate=False):
        if autoUpdate:
            self.invalidateScreenshot()
        _, exc = self._fmbtExec(statement)
        if autoUpdate:
            self.scheduleUpdateScreenshot(1.0)
        return exc == None

    def setFilename(self, filename):
        self._scriptFilename = filename

    def save(self):
        if self._scriptFilename:
            file(self._scriptFilename, "w").write(self.editor.toPlainText())
        else:
            return self.saveAs()
        self.autoConnect()

    def newAndroid(self):
        self._newScript("import fmbtandroid\n"
                        "sut = fmbtandroid.Device()")

    def newTizen(self):
        self._newScript("import fmbttizen\n"
                        "sut = fmbttizen.Device()")

    def newX11(self):
        self._newScript("import fmbtx11\n"
                        "sut = fmbtx11.Screen()")

    def newVNC(self):
        self._newScript("import fmbtvnc\n"
                        "sut = fmbtvnc.Screen()")

    def _newScript(self, script):
        self.editor.setPlainText(script)
        _app.processEvents()
        for _ in xrange(script.index("(")+1):
            self.editor.moveCursor(QtGui.QTextCursor.Right, QtGui.QTextCursor.MoveAnchor)
        self.editor.setFocus()
        if self.autoConnect():
            self.scheduleUpdateScreenshot(0.1)

    def autoConnect(self):
        # recognize fmbt imports and GTI instantiation
        oldMod = self._autoConnectModules
        oldGti = self._autoConnectGti
        script = self.editor.toPlainText()
        self._autoConnectModules = _g_importFmbtRE.findall(script)
        self._autoConnectGti = _g_gtiInstantiateRE.findall(script)
        if oldGti != self._autoConnectGti:
            if oldMod != self._autoConnectModules:
                for m in self._autoConnectModules:
                    self._fmbtExec("import fmbt" + m)
            if self._autoConnectGti:
                rv, exc = self._fmbtExec(self._autoConnectGti[0][0])
                if exc == None:
                    # connected successfully
                    self._sut = self._autoConnectGti[0][1]
            else:
                self._sut = None
        return self._sut != None # return True if connected

    def saveAs(self):
        path = QtGui.QFileDialog.getSaveFileName(
            self, "Save script", '', ";;".join(self._scriptFileFormats))
        newName = path[0]
        if str(newName) == "":
            return False
        else:
            self._scriptFilename = newName
        return self.save()

    def askBitmapFilename(self, suggestion):
        path = QtGui.QFileDialog.getSaveFileName(
            self, "Save bitmap", '', ";;".join(self._bitmapFileFormats))
        newName = path[0]
        if str(newName) == "":
            return None
        else:
            return newName

    def renameBitmap(self, origName, newName):
        cursor = self.editor.textCursor()
        cursor.select(QtGui.QTextCursor.LineUnderCursor)
        l = cursor.selectedText()
        if '"%s"' % (origName,) in l:
            l = l.replace('"%s"' % (origName,), '"%s"' % (newName,))
            cursor.insertText(l)

    def open(self):
        dialog = QtGui.QFileDialog()
        dialog.setDirectory(os.getcwd())
        dialog.setWindowTitle("Open script")
        dialog.setNameFilters(self._scriptFileFormats)
        dialog.exec_()
        if not dialog.result():
            return
        filepath = str(dialog.selectedFiles()[0])
        self._scriptFilename = str(dialog.selectedFiles()[0])
        self.editor.setPlainText(file(self._scriptFilename).read())

    def _fmbtExec(self, statement, silent=False):
        if not silent or opt_debug:
            log("executing: %s" % (statement,))
        try:
            exec statement in self._fmbtEnv
        except Exception, e:
            if not silent or opt_debug:
                log("exception: %s\n  %s" %
                    (e, "    \n".join(traceback.format_exc().splitlines())))
            return None, e
        return None, None

    def _fmbtEval(self, expression, silent=False):
        if not silent or opt_debug:
            log("evaluating: %s" % (expression,))
        try:
            rv = eval(expression, self._fmbtEnv, self._fmbtEnv)
            if opt_debug:
                log("returned %s: %s" % (type(rv), rv))
        except Exception, e:
            if not silent or opt_debug:
                log("exception: %s" % (e,))
            return None, e
        return rv, None

    def updateScreenshot(self):
        self.invalidateScreenshot()
        if self._sut == None:
            self.autoConnect()
        if self._sut != None:
            rv, exc = self._fmbtExec('%s.refreshScreenshot().save("screen2gti.png")' % (self._sut))
            if exc == None:
                self.screenshotImage = QtGui.QImage()
                self.screenshotImage.load("screen2gti.png")
        self.updateScreenshotView()
        self.editor.setFocus()

    def updateScreenshotView(self):
        self.screenshotQLabel.setPixmap(
            QtGui.QPixmap.fromImage(
                self.screenshotImage))
        self.screenshotContainer.area.setWidget(self.screenshotQLabel)
        self.screenshotContainer.area.wheel_scale_changed()
        self.screenshotButtonRefresh.setChecked(False)

    def addAPICall(self, call, cursorOffset=0):
        cursor = self.editor.textCursor()
        txt = self.editor.toPlainText()
        lineBeforeCursor = txt[cursor.block().position():cursor.position()]
        if lineBeforeCursor.strip() == "":
            cursor.beginEditBlock()
            cursor.insertText(self._sut + "." + call)
            cursor.endEditBlock()
            if cursorOffset < 0:
                for _ in xrange(abs(cursorOffset)):
                    self.editor.moveCursor(QtGui.QTextCursor.Left, QtGui.QTextCursor.MoveAnchor)
            else:
                for _ in xrange(abs(cursorOffset)):
                    self.editor.moveCursor(QtGui.QTextCursor.Right, QtGui.QTextCursor.MoveAnchor)

    def verifyBitmap(self, filepath=None):
        if self.editorButtonRec.isChecked():
            self.addAPICall('verifyBitmap("noname.png")', -1)
            self.selectBitmap()
            return
        if filepath == None:
            filename = self.bitmapStringAt()
            if filename:
                filepath = self.bitmapFilepath(filename)
                if filepath == None:
                    log('bitmap "%s" not in bitmapPath' % (filename,))
            else:
                log("no bitmap to verify")
        if filepath != None:
            log('verifying bitmap "%s"' % (filepath,))
            items, exc = self._fmbtEval(
                '%s.screenshot().findItemsByBitmap("%s")' % (
                self._sut, filename))
            if items:
                log('bitmap "%s" found at %s' % (filename, items[0].bbox()))
                self.drawRect(*items[0].bbox())
            else:
                log('bitmap "%s" not found' % (filename,))

    def tapBitmap(self, filepath=None):
        if self.editorButtonRec.isChecked():
            self.addAPICall('tapBitmap("noname.png")', -1)
            self.selectBitmap()
            return
        if filepath == None:
            filename = self.bitmapStringAt()
            if filename:
                filepath = self.bitmapFilepath(filename)
                if filepath == None:
                    log('bitmap "%s" not in bitmapPath' % (filename,))
            else:
                log("no bitmap to tap")
        if filepath != None:
            log('tapping bitmap "%s"' % (filepath,))
            rv, exc = self._fmbtEval('%s.tapBitmap("%s")' % (
                self._sut, filename))
            if rv:
                log('bitmap "%s" tapped' % (filename, items[0].bbox()))
                self.drawRect(*items[0].bbox())
            else:
                log('bitmap "%s" not found' % (filename,))

    def swipeBitmap(self, filepath=None):
        if self.editorButtonRec.isChecked():
            self.addAPICall('swipeBitmap("noname.png", "east")', -9)
            self.selectBitmap()
            return

    def editorCursorPositionChanged(self):
        bmFilename = self.bitmapStringAt()
        if bmFilename:
            self.screenshotButtonSelect.setText("Select %s" % (os.path.basename(bmFilename)))
            self.screenshotButtonSelect.setEnabled(True)
        else:
            self.screenshotButtonSelect.setText("Select")
            self.screenshotButtonSelect.setEnabled(False)

    def controlDevice(self):
        if self.screenshotButtonControl.isChecked():
            if self._selectingBitmap:
                self.selectBitmapStop()
                self.screenshotButtonControl.setChecked(True)

    def selectBitmapStop(self):
        if self._selectingBitmap != None:
            log('selecting bitmap "%s" canceled' % (self._selectingBitmap,))
            self._selectingBitmap = None
        self.drawRect(0, 0, 0, 0, True)
        self.screenshotButtonSelect.setChecked(False)
        self.screenshotButtonControl.setChecked(
            self._selectingToggledInteract)
        self._screenshotImageOrig = None
        self.editor.setFocus()

    def selectBitmapDone(self, left, top, right, bottom):
        if left > right:
            left, right = right, left
        if top > bottom:
            top, bottom = bottom, top
        if not (-1 < top < bottom < self.screenshotImage.height() and
                 -1 < left < right < self.screenshotImage.width()):
            log('illegal selection')
            self.selectBitmapStop()
            return None
        self.drawRect(left, top, right, bottom, True)
        selectedImage = self.screenshotImage.copy(left, top, (right-left), (bottom-top))

        if self._selectingBitmap == "noname.png":
            newName = self.askBitmapFilename(self._selectingBitmap)
            if not newName:
                self.selectBitmapStop()
            if newName !=  self._selectingBitmap:
                newName = os.path.basename(newName)
                self.renameBitmap(self._selectingBitmap, newName)
                self._selectingBitmap = newName

        if selectedImage.save(self._selectingBitmap):
            log('saved bitmap "%s"' % (self._selectingBitmap,))
            fullscreenFilename = self._selectingBitmap + ".fullscreen.png"
            if not self.screenshotImage.save(fullscreenFilename):
                log('failed saving fullscreen version "%s"' % (fullscreenFilename,))
        else:
            log('saving bitmap "%s" failed.' % (self._selectingBitmap,))
        self._selectingBitmap = None
        self.selectBitmapStop()

    def selectBitmap(self, filepath=None):
        if self._selectingBitmap:
            self.selectBitmapStop()
            return None

        if filepath == None:
            filename = self.bitmapStringAt()
            if filename:
                filepath = self.bitmapFilepath(filename)
                if filepath:
                    log('select replacement for "%s"' % (filepath,))
                else:
                    filepath = os.path.join(
                        self._fmbtEval('%s._paths.bitmapPath.split(":")[0]' % (self._sut))[0],
                        filename)
                    log('select new bitmap "%s"' % (filepath,))
                self._selectingBitmap = filepath
            else:
                log('use this when the cursor is on bitmap name like "apps.png"')
        elif filepath != None:
            log('select bitmap "%s"' % (filepath,))
            self._selectingBitmap = filepath

        if self._selectingBitmap:
            self.screenshotButtonSelect.setChecked(True)
            self._selectingToggledInteract = self.screenshotButtonControl.isChecked()
            self.screenshotButtonControl.setChecked(False)
        else:
            self.screenshotButtonSelect.setChecked(False)

    def drawRect(self, left, top, right, bottom, clear=False):
        if getattr(self, "_screenshotImageOrig", None) == None:
            self._screenshotImageOrig = self.screenshotImage.copy()
        else:
            self.screenshotImage = self._screenshotImageOrig.copy()
        if not clear:
            x1, y1, x2, y2 = left, top, right, bottom
            w, h = (right-left), (bottom-top)
            painter = QtGui.QPainter(self.screenshotImage)
            bgPen = QtGui.QPen(QtGui.QColor(0, 0, 0), 1)
            fgPen = QtGui.QPen(QtGui.QColor(128, 255, 128), 1)
            painter.setPen(bgPen)
            painter.drawRect(x1-2, y1-2, w+4, h+4)
            painter.drawRect(x1, y1, w, h)
            painter.setPen(fgPen)
            painter.drawRect(x1-1, y1-1, w+2, h+2)
        self.updateScreenshotView()

    def zoomInEditor(self):
        self.editor._scaleevents.changeScale(1.1)

    def zoomOutEditor(self):
        self.editor._scaleevents.changeScale(0.9)

    def zoomInScreenshot(self):
        self.screenshotQLabel._scaleevents.changeScale(1.1)

    def zoomOutScreenshot(self):
        self.screenshotQLabel._scaleevents.changeScale(0.9)


if __name__ == "__main__":

    opt_connect = ""
    opt_gti = None
    opt_sut = None
    opt_debug = 0
    supported_platforms = ['android', 'tizen', 'x11', 'vnc', 'dummy']

    opts, remainder = getopt.getopt(
        sys.argv[1:], 'hd:p:',
        ['help', 'device=', 'platform=', 'debug'])

    for opt, arg in opts:
        if opt in ['-h', '--help']:
            print __doc__
            sys.exit(0)
        elif opt in ['--debug']:
            opt_debug += 1
        elif opt in ['-d', '--device']:
            opt_connect = arg
        elif opt in ['-p', '--platform']:
            opt_gti = arg
            if arg in ['android', 'tizen', 'dummy']:
                opt_gticlass = "Device"
            elif arg in ['x11', 'vnc']:
                opt_gticlass = "Screen"
            else:
                error('unknown platform: "%s". Use one of "%s"' % (
                    arg, '", "'.join(supported_platforms)))

    script = ""
    if remainder:
        scriptFilename = remainder[0]
        try:
            script = file(scriptFilename).read()
        except:
            error('cannot read file "%s"' % (remainder[0],))
    else:
        scriptFilename = None

    _app = QtGui.QApplication(sys.argv)
    _win = MainWindow()
    _win.resize(640, 480)

    if opt_gti == "dummy":
        initSequence = "# sut = fmbtdummy.Device(...)\n"
        sut = fmbtdummy.Device(screenshotList = opt_connect.split(","))
        opt_sut = "sut"
    else:
        initSequence = ""

    if script:
        _win.editor.append(script)
        _win.setFilename(scriptFilename)
    else:
        _win.editor.append(initSequence)
    if _win.autoConnect():
        _win.scheduleUpdateScreenshot(1.0)
    _win.show()
    _app.exec_()
