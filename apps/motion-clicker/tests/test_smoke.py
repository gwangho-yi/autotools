def test_main_window_constructs(qtbot):
    from ui.main_window import MainWindow

    win = MainWindow()
    qtbot.addWidget(win)
    # 포인트 목록이 비어 있는 상태로 정상 생성되는지
    assert win._list.count() == 0
    # IpcServer 스레드가 run()에 진입해 _running=True를 세팅하기 전에 close()가
    # stop()→wait()을 부르면 start/stop 레이스로 데드락한다. 스레드가 기동할
    # 시간을 준 뒤 닫아 레이스를 회피한다.
    qtbot.wait(200)
    win.close()
