#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
======================
@author:Zcnwei
@time:2024/3/22 16:56
=====================
"""
import re
import os
import json
from rtrpcLib import levels
from configure import constants
from configure.constants import State
from rtrpcLib.common import print_with_time
from configure.constants import ResetButtonQSS, UserPng, ResetPng
from gui.resources.style import Color
from gui.controller.login import LoginController
from gui.controller.slots import SlotsController
from PySide6.QtGui import QPixmap, QRegularExpressionValidator, QIcon, QKeySequence, QTextCursor
from PySide6.QtCore import Qt, QObject, QSize, QRegularExpression, QTimer, Signal
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGroupBox, QPushButton,
    QGridLayout, QLineEdit, QSpacerItem, QSizePolicy, QComboBox
)
# Added imports for Step Debug dialog and RPC
import zmq
from PySide6.QtWidgets import QDialog, QMessageBox, QTextEdit
from rtrpcLib import zmqports
from rtrpcLib.rpc.rpc_client import RPCClientWrapper
from rtrpcLib.rpc.publisher import NoOpPublisher
from rtrpcLib.rpc.tinyrpc.protocols.jsonrpc import JSONRPCErrorResponse


class ScanController(QObject):
    _signalLoop = Signal(bool)

    def __init__(self, signalBox=None):
        super().__init__()
        self._signalBox = signalBox
        self._looping = False
        self.reporter = None
        self._bufferETravelers = None
        self._timer = QTimer()
        self._timer.timeout.connect(self.nextCycle)
        self.slotsC = SlotsController(slots=constants.SLOTS)
        self.view = ScanView(self.slotsC.view)
        self.user = "NONE-Administrator"  ## just debug
        self.user_home = os.path.expanduser('~')
        f = open(f"{self.user_home}/testerconfig/config.json", 'r')
        self.gh_info = json.load(f)
        self.is_auto_scan = self.gh_info.get('autoscan')
        self.changeMode(self.user)
        # Wire Step Debug button
        self.view.buttonStepDebug.clicked.connect(self.openStepDebugDialog)

    def messageBox(self, msg, level=levels.INFO):
        if self._signalBox:
            self._signalBox.emit(msg, level)
        else:
            print_with_time(msg)
    @property
    def looping(self):
        return self._looping

    @property
    def loopAction(self):
        return self.view.selectLoopAction.currentText()

    def updateSn(self, mlbSn:str):
        if constants.CHECK_SN_LENGTH:
            if len(mlbSn) != constants.SN_LENGTH:
                self.clearScanText()
                self.setFocusScan()
                return self.messageBox(f"MLB: {mlbSn} Length is not {constants.SN_LENGTH}", level=levels.WARNING)
            if constants.CHECK_SN_PATTERN:
                if not re.match(constants.SN_PATTERN, mlbSn):
                    self.clearScanText()
                    self.setFocusScan()
                    return self.messageBox(f"MLB: {mlbSn} is not right,pls check", level=levels.WARNING)
        targetIndex = None
        for index in range(constants.SLOTS):
            currState = self.slotsC.currState(index)
            tmpSN = self.slotsC.currText(index)
            if currState == State.DISABLE:
                continue
            elif currState == State.READY and mlbSn.strip().upper() == tmpSN:
                self.clearScanText()
                self.setFocusScan()
                return self.messageBox(f"Repeated MLB: {mlbSn}", level=levels.WARNING)
            elif targetIndex is None and currState not in (State.READY, State.RUNNING):
                targetIndex = index
        if isinstance(targetIndex, int):
            self.slotsC.setText(targetIndex, mlbSn)
            self.slotsC.setState(targetIndex,State.READY)
            # 同步到 Sequencer 的全局变量，确保 [[scanned_sn]] 可被解析
            try:
                self._sync_sn_to_sequencer(targetIndex, mlbSn)
            except Exception:
                pass
        self.clearScanText()
        self.setFocusScan()

    def _get_proxy(self, site: int):
        # 复用 step 调试对话框的RPC策略，缓存各site的代理
        if not hasattr(self, "_proxies"):
            self._proxies = {}
        try:
            if site in self._proxies:
                return self._proxies[site]
            ctx = zmq.Context().instance()
            url = constants.DEFAULT_TRANSPORT_PROTOCOL_CLIENT + str(zmqports.SEQUENCER_PORT + site)
            pub = NoOpPublisher()
            proxy = RPCClientWrapper(url, pub, ctx).remote_server()
            self._proxies[site] = proxy
            return proxy
        except Exception:
            return None

    def _sync_sn_to_sequencer(self, site: int, sn: str):
        # 仅在有有效SN与可用RPC时执行；失败不影响UI
        try:
            proxy = self._get_proxy(site)
            if proxy is not None and sn:
                proxy.set_global('scanned_sn', sn)
        except Exception:
            pass

    def isReady(self):
        if self._looping and self._bufferETravelers:
            return self._bufferETravelers
        e_travelers = dict()
        for index in range(constants.SLOTS):
            currState = self.slotsC.currState(index)
            if currState not in (State.READY, State.DISABLE):
                return None
            elif currState == State.READY:
                currSn = self.slotsC.currText(index)
                e_travelers.setdefault(str(index), {"attributes": {"MLBSN": currSn, "cfg": ""}})
        return e_travelers

    def startTest(self, e_travelers=None):
        self._bufferETravelers = e_travelers or self._bufferETravelers
        self.view.buttonStart.setEnabled(False)
        self.view.lineEditSn.setEnabled(False)
        self.view.lineEditSn.setText("")
        self.view.buttonLoad.setEnabled(False)
        self.view.buttonReLoad.setEnabled(False)
        if not self._looping:
            self.view.buttonLoop.setEnabled(False)

    def endTest(self, result):
        self.changeMode(self.user)
        self.view.buttonStart.setEnabled(True)
        if not self.is_auto_scan:
            self.view.lineEditSn.setEnabled(True)
            self.view.lineEditSn.setFocus()
        self.checkLoop()

    def startLoop(self):
        self._looping = True
        self.view.buttonLoop.setEnabled(True)
        self.view.buttonLoop.setText("Loop Out")
        self.view.buttonStart.setEnabled(False)
        
    def stopLoop(self):
        self._looping = False
        self.view.buttonLoop.setText("Loop In")
    
    def checkLoop(self):
        if not self._looping:
            self._bufferETravelers = None
            return False
        loopCount = int(self.view.lineEditLoopCount.text()) - 1
        if loopCount <= 0:
            self.changeMode(self.user)
            self.view.lineEditLoopCount.setText("0")
            self.view.buttonLoop.setText("Loop In")
            self.view.buttonStart.setEnabled(True)
            self.view.lineEditSn.setEnabled(True)
            self.view.lineEditSn.setFocus()
            self._bufferETravelers = None
            self._looping = False
            return False
        else:
            self.view.lineEditLoopCount.setText(f"{loopCount}")
            duration = int(self.view.lineEditLoopDuration.text())
            self._timer.start(duration)
        return True

    def nextCycle(self):
        self._timer.stop()
        flag = self.loopAction != "Normal"
        self._signalLoop.emit(flag)

    def login(self):
        user = "Operator"
        if self.view.buttonLogin.text() == "Login":
            if LoginController.get_password():
                user = "Administrator"
        return self.changeMode(user)

    def changeMode(self, user):
        if user == "Administrator":
            self.view.buttonLogin.setText("Logout")
            self.view.labCurrUser.setText("Administrator")
            self.view.labCurrUser.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.view.buttonLoad.setEnabled(True)
            self.view.buttonReLoad.setEnabled(True)
            self.view.buttonLoop.setEnabled(True)
            self.view.stopOnFail.setEnabled(True)
        else:
            self.view.buttonLogin.setText("Login")
            self.view.labCurrUser.setText("Operator")
            self.view.labCurrUser.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.view.buttonLoad.setEnabled(False)
            self.view.buttonReLoad.setEnabled(False)
            self.view.buttonLoop.setEnabled(False)
            self.view.stopOnFail.setEnabled(False)
        self.user = user

    # Added: open Step Debug dialog
    def openStepDebugDialog(self):
        try:
            if not hasattr(self, '_stepDebugDlg') or self._stepDebugDlg is None:
                self._stepDebugDlg = StepDebugDialog(self)
            self._stepDebugDlg.show()
            self._stepDebugDlg.raise_()
        except Exception as e:
            self.messageBox(f"Open Step Debug failed: {e}", level=levels.ERROR)

    def updateYield(self, result):
        passCount = int(self.view.labPassCount.text())
        failCount = int(self.view.labFailCount.text())
        passCount = passCount + 1 if result else passCount
        failCount = failCount if result else failCount + 1
        totalCount = passCount + failCount
        passRate = round((passCount / totalCount) * 100, 2)
        failRate = round((failCount / totalCount) * 100, 2)
        self.view.labPassCount.setText(f"{passCount}")
        self.view.labFailCount.setText(f"{failCount}")
        self.view.labTotalCount.setText(f"{totalCount}")
        self.view.labPassRate.setText(f"{passRate}%")
        self.view.labFailRate.setText(f"{failRate}%")

    def cleanScanText(self):
        self.view.lineEditSn.setText("")
    
    def clearScanText(self):
        # Compatibility alias: earlier code calls clearScanText()
        # Delegate to the existing cleanScanText implementation
        self.cleanScanText()
    
    def setFocusScan(self):
        self.view.lineEditSn.setFocus()


class ScanView(QFrame):
    def __init__(self, slotsView):
        super(ScanView, self).__init__()
        self.mainLayout = QVBoxLayout()
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(5)
        self.mainLayout.addWidget(slotsView)
        ## lineEdit
        self.lineEditSn = None
        self.lineEditLoopCount = None
        self.lineEditLoopDuration = None
        self.selectLoopAction = None
        ## button
        self.buttonLogin = None
        self.buttonReset = None
        self.buttonLoad = None
        self.buttonReLoad = None
        self.buttonLoop = None
        self.buttonLogPath = None
        self.stopOnFail = None
        self.buttonStart = None
        self.buttonStop = None
        ## text label
        self.labPassCount = None
        self.labFailCount = None
        self.labTotalCount = None
        self.labPassRate = None
        self.labFailRate = None
        self.labCurrUser = None
        self.labFixtureText = None
        self.labUserText = None
        self.labOverlay = None
        ## widgets layout
        self.yieldLayout()
        self.controlLayout()
        # self.infoLayout()
        self.snScanLayout()
        self.setLayout(self.mainLayout)
        self.setFrameShape(QFrame.Shape.Box)
        self.setFrameShadow(QFrame.Shadow.Raised)

    def controlLayout(self):
        loginBox = QGroupBox()
        subLayout = QVBoxLayout(loginBox)
        subLayout.setContentsMargins(0, 0, 0, 0)
        subLayout.setSpacing(0)

        top1Layout = QHBoxLayout()
        top1Layout.setSpacing(2)
        top1Layout.setContentsMargins(0, 0, 0, 0)
        labUserPng = QLabel()
        # labUserPng.setFixedSize(40, 40)
        pixMap = QPixmap(UserPng)
        pixMap = pixMap.scaled(QSize(30, 30), Qt.KeepAspectRatio)
        labUserPng.setPixmap(pixMap)
        labUserPng.setAlignment(Qt.AlignCenter)
        labUserPng.setFixedSize(38, 30)
        self.labCurrUser = QLabel("Administrator")
        self.labCurrUser.setFixedSize(90, 30)
        self.labCurrUser.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.buttonLogin = QPushButton("Logout")
        top1Layout.addWidget(labUserPng)
        top1Layout.addWidget(self.labCurrUser)
        top1Layout.addWidget(self.buttonLogin)

        top2Layout = QHBoxLayout()
        top2Layout.setSpacing(2)
        top2Layout.setContentsMargins(0, 0, 0, 0)
        self.buttonLoad = QPushButton("Load")
        self.buttonLoad.setShortcut(QKeySequence(Qt.CTRL | Qt.Key_L))
        self.buttonReLoad = QPushButton("MES")
        self.buttonReLoad.setShortcut(QKeySequence(Qt.CTRL | Qt.Key_R))
        # Added: Step Debug button
        self.buttonStepDebug = QPushButton("StepDebug")
        top2Layout.addWidget(self.buttonLoad)
        top2Layout.addWidget(self.buttonReLoad)
        top2Layout.addWidget(self.buttonStepDebug)

        top3Layout = QHBoxLayout()
        top3Layout.setSpacing(2)
        top3Layout.setContentsMargins(0, 0, 0, 0)
        self.buttonLoop = QPushButton("Loop In")
        self.buttonLogPath = QPushButton("TestLog")
        self.stopOnFail = QPushButton("autoscan")
        top3Layout.addWidget(self.buttonLoop)
        top3Layout.addWidget(self.buttonLogPath)
        top3Layout.addWidget(self.stopOnFail)

        top4Layout = QGridLayout()
        top4Layout.setSpacing(2)
        top4Layout.setContentsMargins(0, 0, 0, 0)
        labLoopCount = QLabel("LoopCount")
        self.lineEditLoopCount = QLineEdit("5")
        numValidator = QRegularExpressionValidator(QRegularExpression("[0-9]+"))
        self.lineEditLoopCount.setValidator(numValidator)
        labLoopDuration = QLabel("LoopDuration(ms)")
        self.lineEditLoopDuration = QLineEdit("5000")
        self.lineEditLoopDuration.setValidator(numValidator)
        labLoopAction = QLabel("LoopAction")
        self.selectLoopAction = QComboBox()
        self.selectLoopAction.addItems(["Normal", "NoAction"])
        self.selectLoopAction.setCurrentText("Normal")
        top4Layout.addWidget(labLoopAction, 0, 0)
        top4Layout.addWidget(self.selectLoopAction, 0, 1)
        top4Layout.addWidget(labLoopCount, 1, 0)
        top4Layout.addWidget(self.lineEditLoopCount, 1, 1)
        top4Layout.addWidget(labLoopDuration, 2, 0)
        top4Layout.addWidget(self.lineEditLoopDuration, 2, 1)

        subLayout.addLayout(top1Layout)
        subLayout.addLayout(top2Layout)
        subLayout.addLayout(top3Layout)
        subLayout.addLayout(top4Layout)
        self.mainLayout.addWidget(loginBox)

    def infoLayout(self):
        infoBox = QGroupBox()
        subLayout = QVBoxLayout(infoBox)
        subLayout.setContentsMargins(0, 0, 0, 0)
        fixtureID = QLabel("FixtureID:")
        self.labFixtureText = QLabel()
        userID = QLabel("OperatorID:")
        self.labUserText = QLabel()
        overlayID = QLabel("Overlay:")
        self.labOverlay = QLabel()
        subLayout.addWidget(fixtureID)
        subLayout.addWidget(self.labFixtureText)
        subLayout.addWidget(overlayID)
        subLayout.addWidget(self.labOverlay)
        subLayout.addWidget(userID)
        subLayout.addWidget(self.labUserText)
        self.mainLayout.addWidget(infoBox)

    def yieldLayout(self):
        subLayout = QHBoxLayout()
        yieldBox = QGroupBox()
        leftLayout = QVBoxLayout()
        self.buttonReset = QPushButton()
        if constants.PLATFORM == "Darwin":
            self.buttonReset.setStyleSheet(ResetButtonQSS)
        else:
            self.buttonReset.setIcon(QIcon(ResetPng))
            self.buttonReset.setIconSize(QSize(20, 20))
        self.buttonReset.setFixedSize(25, 25)
        self.buttonReset.clicked.connect(self.clean)
        labPass = QLabel("PASS:")
        labFail = QLabel("FAIL:")
        labTotal = QLabel("Total:")
        leftLayout.addWidget(self.buttonReset, 1)
        leftLayout.addWidget(labPass)
        leftLayout.addWidget(labFail)
        leftLayout.addWidget(labTotal)
        leftLayout.setContentsMargins(0, 0, 0, 0)
        leftLayout.setSpacing(0)

        middleLayout = QVBoxLayout()
        lbl_fail_1 = QLabel("Tested:")
        self.labPassCount = QLabel("0")
        self.labFailCount = QLabel("0")
        self.labTotalCount = QLabel("0")
        middleLayout.addWidget(lbl_fail_1)
        middleLayout.addWidget(self.labPassCount)
        middleLayout.addWidget(self.labFailCount)
        middleLayout.addWidget(self.labTotalCount)
        middleLayout.setContentsMargins(0, 0, 0, 0)
        middleLayout.setSpacing(0)

        rightLayout = QVBoxLayout()
        labRate = QLabel("Rate:")
        self.labPassRate = QLabel("0%")
        self.labPassRate.setStyleSheet(Color.green)
        self.labFailRate = QLabel("0%")
        self.labFailRate.setStyleSheet(Color.red)
        labTotalRate = QLabel()
        rightLayout.addWidget(labRate)
        rightLayout.addWidget(self.labPassRate)
        rightLayout.addWidget(self.labFailRate)
        rightLayout.addWidget(labTotalRate)
        rightLayout.setSpacing(0)
        rightLayout.setContentsMargins(0, 0, 0, 0)

        subLayout.addLayout(leftLayout)
        subLayout.addLayout(middleLayout)
        subLayout.addLayout(rightLayout)
        subLayout.setSpacing(0)
        subLayout.setContentsMargins(0, 0, 0, 0)
        yieldBox.setFixedHeight(80)
        yieldBox.setFixedWidth(230)
        yieldBox.setLayout(subLayout)
        self.mainLayout.addWidget(yieldBox)

    def clean(self):
        self.labPassCount.setText('0')
        self.labFailCount.setText('0')
        self.labTotalCount.setText('0')
        self.labPassRate.setText('0%')
        self.labFailRate.setText('0%')

    def snScanLayout(self):
        space = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.mainLayout.addItem(space)
        scanLayout = QGridLayout()
        scanLayout.setContentsMargins(1, 1, 1, 1)
        self.lineEditSn = QLineEdit()
        snValidator = QRegularExpressionValidator(QRegularExpression("[a-zA-Z0-9]+"))
        self.lineEditSn.setValidator(snValidator)
        self.lineEditSn.setFocus()
        self.buttonStart = QPushButton("Start (F5)")
        self.buttonStart.setShortcut(QKeySequence(Qt.Key_F5))
        self.buttonStop = QPushButton("Stop")
        # self.buttonStop.setShortcut(QKeySequence(Qt.Key_F6))
        scanLayout.addWidget(self.lineEditSn, 0, 0, 1, 2)
        scanLayout.addWidget(self.buttonStart, 1, 0, 1, 1)
        scanLayout.addWidget(self.buttonStop, 1, 1, 1, 1)
        self.mainLayout.addLayout(scanLayout)


if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    ui = ScanController()
    # ui.startTest()
    ui.view.show()
    sys.exit(app.exec())

# Added: StepDebugDialog definition
class StepDebugDialog(QDialog):
    def __init__(self, scan_ctrl=None):
        super().__init__()
        self.setWindowTitle("Sequencer Step Debug")
        self.setMinimumSize(420, 220)
        self.setWindowIcon(QIcon(constants.ICONPATH))
        self._proxies = {}
        self.scan_ctrl = scan_ctrl
        main = QVBoxLayout(self)
        top = QHBoxLayout()
        lblSite = QLabel("Site:")
        self.comboSite = QComboBox()
        self.comboSite.addItems([str(i) for i in range(constants.SLOTS)])
        top.addWidget(lblSite)
        top.addWidget(self.comboSite)
        # SN input
        snLay = QHBoxLayout()
        lblSn = QLabel("SN:")
        self.editSn = QLineEdit()
        # 优化输入体验
        try:
            self.editSn.setClearButtonEnabled(True)
            self.editSn.setFocusPolicy(Qt.ClickFocus | Qt.StrongFocus)
        except Exception:
            pass
        snLay.addWidget(lblSn)
        snLay.addWidget(self.editSn)
        # Jump input
        jumpLay = QHBoxLayout()
        lblJump = QLabel("Jump:")
        self.editJump = QLineEdit()
        jumpLay.addWidget(lblJump)
        jumpLay.addWidget(self.editJump)
        # Buttons
        btnLay = QHBoxLayout()
        self.btnStep = QPushButton("Step")
        self.btnJump = QPushButton("Jump")
        self.btnSkip = QPushButton("Skip")
        # 防止在对话框中按下 Enter 触发默认按钮（Step）
        try:
            for btn in (self.btnStep, self.btnJump, self.btnSkip):
                btn.setAutoDefault(False)
                btn.setDefault(False)
        except Exception:
            pass
        btnLay.addWidget(self.btnStep)
        btnLay.addWidget(self.btnJump)
        btnLay.addWidget(self.btnSkip)
        # Assemble
        main.addLayout(top)
        main.addLayout(snLay)
        main.addLayout(jumpLay)
        main.addLayout(btnLay)
        # Logs display area: show CB_PUB and BMT_PUB with different colors
        logsLay = QVBoxLayout()
        lblLogs = QLabel("PUB Logs (CB_PUB blue, BMT_PUB green)")
        self.textLogs = QTextEdit()
        try:
            self.textLogs.setReadOnly(True)
            self.textLogs.setAcceptRichText(True)
            self.textLogs.setStyleSheet("font-family: Menlo, Consolas, monospace; font-size: 12px;")
        except Exception:
            pass
        logsBar = QHBoxLayout()
        logsBar.addWidget(lblLogs)
        self.btnClearLogs = QPushButton("clear logs")
        logsBar.addStretch()
        logsBar.addWidget(self.btnClearLogs)
        logsLay.addLayout(logsBar)
        logsLay.addWidget(self.textLogs)
        main.addLayout(logsLay)
        # Signals
        self.btnStep.clicked.connect(self.on_step)
        self.btnJump.clicked.connect(self.on_jump)
        self.btnSkip.clicked.connect(self.on_skip)
        self.comboSite.currentIndexChanged.connect(lambda _: self._sync_sn_from_main())
        # 切换站位时更新订阅
        self.comboSite.currentIndexChanged.connect(lambda _: self._switch_site_subscribers())
        # 清空日志按钮
        try:
            self.btnClearLogs.clicked.connect(self.on_clear_logs)
        except Exception:
            pass
        # 当 SN 输入结束（按下回车或失去焦点）时，立即应用到 Sequencer 与主界面
        try:
            self.editSn.returnPressed.connect(self.on_sn_commit)
            self.editSn.editingFinished.connect(self.on_sn_commit)
        except Exception:
            pass
        # Initialize SN from main UI if available
        self._sync_sn_from_main()
        # 初始化 PUB 订阅与轮询器
        try:
            self._poller = zmq.Poller()
            self._sub_socks = []
            self._subTimer = QTimer(self)
            self._subTimer.timeout.connect(self._poll_subscribers)
            # 初始站位订阅
            try:
                site = int(self.comboSite.currentText())
            except Exception:
                site = 0
            self._setup_subscribers_for_site(site)
            self._subTimer.start(100)
        except Exception:
            pass

    def _get_proxy(self, site: int):
        if site in self._proxies:
            return self._proxies[site]
        ctx = zmq.Context().instance()
        url = constants.DEFAULT_TRANSPORT_PROTOCOL_CLIENT + str(zmqports.SEQUENCER_PORT + site)
        pub = NoOpPublisher()
        proxy = RPCClientWrapper(url, pub, ctx).remote_server()
        self._proxies[site] = proxy
        return proxy

    def _error(self, text: str):
        QMessageBox.warning(self, "Sequencer", text)

    def _get_main_ui_sn(self, site: int) -> str:
        try:
            if self.scan_ctrl is not None:
                return str(self.scan_ctrl.slotsC.currText(site))
        except Exception:
            pass
        return ''

    def _sync_sn_from_main(self):
        try:
            site = int(self.comboSite.currentText())
        except Exception:
            site = 0
        sn = self._get_main_ui_sn(site)
        if sn:
            self.editSn.setText(sn)

    def _apply_sn(self, site: int):
        sn = self.editSn.text().strip()
        if not sn:
            sn = self._get_main_ui_sn(site)
            if sn:
                self.editSn.setText(sn)
        if not sn:
            return
        # 2) 同步到主界面槽位文本（确保UI也“拿到”这个SN）
        try:
            if self.scan_ctrl is not None:
                self.scan_ctrl.slotsC.setText(site, sn)
                curr = self.scan_ctrl.slotsC.currState(site)
                # 若当前不是 READY/RUNNING/DISABLE，则置为 READY，方便后续开始测试或调试
                if curr not in (State.READY, State.RUNNING, State.DISABLE):
                    self.scan_ctrl.slotsC.setState(site, State.READY)
        except Exception:
            pass
        # 1) 传递给 Sequencer 的全局变量（即使RPC失败也不影响UI更新）
        try:
            proxy = self._get_proxy(site)
            proxy.set_global('scanned_sn', sn)
        except Exception:
            pass

    def on_step(self):
        try:
            # 在每次 Step 前插入分隔标识，便于区分每次 step 的日志（不计数）
            try:
                self.textLogs.insertHtml('<br/><span style="color:#808080">===== STEP =====</span>'
                                         '<hr style="border:0;border-top:1px solid #808080;margin:4px 0;"/>')
                self._scroll_logs_to_bottom()
            except Exception:
                pass
            site = int(self.comboSite.currentText())
            # 先应用SN到UI与Sequencer（Sequencer失败不影响UI）
            self._apply_sn(site)
            proxy = self._get_proxy(site)
            ret = proxy.step()
            if isinstance(ret, JSONRPCErrorResponse):
                self._error(f"[Site {site}] Step Error: {ret.error}")
        except Exception as e:
            self._error(f"[Site {self.comboSite.currentText()}] Step Exception: {e}")

    def on_jump(self):
        target = self.editJump.text().strip()
        if not target:
            self._error("请输入跳转目标（行号或标签）")
            return
        try:
            site = int(self.comboSite.currentText())
            # 先应用SN到UI与Sequencer（Sequencer失败不影响UI）
            self._apply_sn(site)
            proxy = self._get_proxy(site)
            arg = int(target) if target.isdigit() else target
            ret = proxy.jump(arg)
            if isinstance(ret, JSONRPCErrorResponse):
                self._error(f"[Site {site}] Jump Error: {ret.error}")
        except Exception as e:
            self._error(f"[Site {self.comboSite.currentText()}] Jump Exception: {e}")

    def on_skip(self):
        try:
            site = int(self.comboSite.currentText())
            # 先应用SN到UI与Sequencer（Sequencer失败不影响UI）
            self._apply_sn(site)
            proxy = self._get_proxy(site)
            ret = proxy.skip()
            if isinstance(ret, JSONRPCErrorResponse):
                self._error(f"[Site {site}] Skip Error: {ret.error}")
        except Exception as e:
            self._error(f"[Site {self.comboSite.currentText()}] Skip Exception: {e}")

    def on_sn_commit(self):
        try:
            site = int(self.comboSite.currentText())
        except Exception:
            site = 0
        # 不依赖RPC，确保UI能立即拿到SN
        self._apply_sn(site)

    def keyPressEvent(self, event):
        # 拦截 Enter/Return：当焦点在 SN 输入框时，仅提交 SN，不触发任何默认按钮
        try:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and self.editSn.hasFocus():
                self.on_sn_commit()
                event.accept()
                return
        except Exception:
            pass
        super().keyPressEvent(event)

    # ---- PUB subscribers (CB_PUB/BMT_PUB) ----
    def _switch_site_subscribers(self):
        try:
            site = int(self.comboSite.currentText())
        except Exception:
            site = 0
        # 切换时先停止轮询，避免旧订阅与新订阅交叉
        try:
            if hasattr(self, "_subTimer"):
                self._subTimer.stop()
        except Exception:
            pass
        # 卸载旧订阅
        self._teardown_subscribers()
        # 重建 Poller，确保干净的注册表
        try:
            self._poller = zmq.Poller()
        except Exception:
            pass
        # 建立新订阅
        self._setup_subscribers_for_site(site)
        # 重启轮询计时器
        try:
            if hasattr(self, "_subTimer"):
                self._subTimer.start(100)
        except Exception:
            pass

    def _setup_subscribers_for_site(self, site: int):
        ctx = zmq.Context().instance()
        addresses = [
            constants.DEFAULT_TRANSPORT_PROTOCOL_CLIENT + str(zmqports.SEQUENCER_PUB + site),
            constants.DEFAULT_TRANSPORT_PROTOCOL_CLIENT + str(zmqports.ARM_PUB + site),
            constants.DEFAULT_TRANSPORT_PROTOCOL_CLIENT + str(zmqports.UART2_PUB + site),
            constants.DEFAULT_TRANSPORT_PROTOCOL_CLIENT + str(zmqports.PRM_GUI_PUB),
        ]
        for addr in addresses:
            try:
                sock = ctx.socket(zmq.SUB)
                sock.connect(addr)
                try:
                    sock.setsockopt(zmq.SUBSCRIBE, zmqports.PUB_CHANNEL)
                except TypeError:
                    sock.setsockopt(zmq.SUBSCRIBE, str(zmqports.PUB_CHANNEL).encode("utf-8"))
                self._poller.register(sock, zmq.POLLIN)
                self._sub_socks.append(sock)
            except Exception:
                pass

    def _teardown_subscribers(self):
        for sock in getattr(self, '_sub_socks', []):
            try:
                self._poller.unregister(sock)
            except Exception:
                pass
            try:
                sock.setsockopt(zmq.LINGER, 0)
                sock.close()
            except Exception:
                pass
        self._sub_socks = []

    def _poll_subscribers(self):
        try:
            socks = dict(self._poller.poll(10))
            for fd, event in list(socks.items()):
                if event == zmq.POLLIN:
                    try:
                        recv_list = fd.recv_multipart(zmq.NOBLOCK)
                        topic, ts, level, origin, data = [part.decode() for part in recv_list]
                        if "CB_PUB_" in origin or "BMT_PUB_" in origin:
                            self._append_pub_line(origin, ts, level, data)
                    except Exception:
                        pass
        except Exception:
            pass

    def _append_pub_line(self, origin: str, ts: str, level: str, data: str):
        color = "#1E90FF" if "CB_PUB_" in origin else "#2E8B57"
        html = f'<span style="color:{color}">[{ts}][{origin}][{level}] {data}</span><br/>'
        try:
            self.textLogs.insertHtml(html)
            self._scroll_logs_to_bottom()
        except Exception:
            try:
                self.textLogs.append(f"[{ts}][{origin}][{level}] {data}")
                self._scroll_logs_to_bottom()
            except Exception:
                pass

    def _scroll_logs_to_bottom(self):
        try:
            # 将光标移动至文本末尾，并确保可见
            self.textLogs.moveCursor(QTextCursor.End)
            try:
                self.textLogs.ensureCursorVisible()
            except Exception:
                pass
            # 直接将滚动条定位到底部
            sb = self.textLogs.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())
            # 再次在下一轮事件循环设置，避免布局刷新导致回弹
            try:
                QTimer.singleShot(0, lambda: (
                    self.textLogs.verticalScrollBar() and
                    self.textLogs.verticalScrollBar().setValue(self.textLogs.verticalScrollBar().maximum())
                ))
            except Exception:
                pass
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            if hasattr(self, "_subTimer"):
                self._subTimer.stop()
        except Exception:
            pass
        self._teardown_subscribers()
        super().closeEvent(event)

    def on_clear_logs(self):
        try:
            self.textLogs.clear()
        except Exception:
            pass