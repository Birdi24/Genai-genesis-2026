//
//  FrausUITests.swift
//  FrausUITests
//
//  Created by Parth Narkhede on 2026-03-14.
//

import XCTest

final class FrausUITests: XCTestCase {

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.

        // In UI tests it is usually best to stop immediately when a failure occurs.
        continueAfterFailure = false

        // In UI tests it’s important to set the initial state - such as interface orientation - required for your tests before they run. The setUp method is a good place to do this.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    @MainActor
    func testExample() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launch()

        // Use XCTAssert and related functions to verify your tests produce the correct results.
    }

    @MainActor
    func testDemoIncomingCallEndToEndFlow() throws {
        let app = XCUIApplication()
        app.launchEnvironment["FRAUS_USE_MOCK_VERIFICATION"] = "false"
        app.launchEnvironment["FRAUS_FALLBACK_TO_MOCK_VERIFICATION"] = "false"
        app.launchEnvironment["FRAUS_BACKEND_BASE_URL"] = "http://127.0.0.1:8001"
        app.launch()

        XCTAssertTrue(app.buttons["Log In"].waitForExistence(timeout: 8))
        app.buttons["Log In"].tap()

        XCTAssertTrue(app.buttons["Continue"].waitForExistence(timeout: 8))
        app.buttons["Continue"].tap()

        let answerButton = app.buttons["Answer in Fraus"].firstMatch
        XCTAssertTrue(answerButton.waitForExistence(timeout: 8))
        answerButton.tap()

        XCTAssertTrue(app.buttons["Check Number"].waitForExistence(timeout: 8))

        let phoneField = app.textFields.element(boundBy: 0)
        XCTAssertTrue(phoneField.waitForExistence(timeout: 5))

        guard let prefilledNumberRaw = phoneField.value as? String else {
            XCTFail("Unable to read prefilled number from Verify Caller field")
            return
        }

        let prefilledDigits = digitsOnly(prefilledNumberRaw)
        XCTAssertFalse(prefilledDigits.isEmpty)

        app.buttons["Check Number"].tap()

        XCTAssertTrue(app.buttons["Transfer to AI Protection"].waitForExistence(timeout: 15))

        let stateTitle = app.descendants(matching: .any)["riskResult.stateTitle"]
        XCTAssertTrue(stateTitle.waitForExistence(timeout: 8))
        XCTAssertTrue(
            ["Suspicious Caller", "Unknown Caller"].contains(stateTitle.label),
            "Expected suspicious/unknown risk result before transfer, got: \(stateTitle.label)"
        )

        XCTAssertTrue(
            waitForStaticTextDigitsMatch(in: app, expectedDigits: prefilledDigits, timeout: 8),
            "Expected risk screen to show the same caller number digits"
        )

        app.buttons["Transfer to AI Protection"].tap()

        XCTAssertTrue(app.buttons["Start AI Protection"].waitForExistence(timeout: 8))
        app.buttons["Start AI Protection"].tap()

        XCTAssertTrue(app.staticTexts["Linked to incoming call"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.descendants(matching: .any)["activeProtection.stateBadge"].waitForExistence(timeout: 8))
    }

    @MainActor
    func testVerifiedNumberDoesNotOfferTransfer() throws {
        let app = XCUIApplication()
        app.launchEnvironment["FRAUS_USE_MOCK_VERIFICATION"] = "true"
        app.launchEnvironment["FRAUS_FALLBACK_TO_MOCK_VERIFICATION"] = "false"
        app.launchEnvironment["FRAUS_BACKEND_BASE_URL"] = "http://127.0.0.1:8001"
        app.launch()

        XCTAssertTrue(app.buttons["Log In"].waitForExistence(timeout: 8))
        app.buttons["Log In"].tap()

        XCTAssertTrue(app.buttons["Continue"].waitForExistence(timeout: 8))
        app.buttons["Continue"].tap()

        let verifyNumberLabel = app.staticTexts["Verify Number"]
        XCTAssertTrue(verifyNumberLabel.waitForExistence(timeout: 8))
        verifyNumberLabel.tap()

        XCTAssertTrue(app.buttons["Check Number"].waitForExistence(timeout: 8))

        let verifiedChip = app.staticTexts["Verified"]
        XCTAssertTrue(verifiedChip.waitForExistence(timeout: 8))
        verifiedChip.tap()

        let phoneField = app.textFields.element(boundBy: 0)
        XCTAssertTrue(phoneField.waitForExistence(timeout: 5))
        replaceText(in: phoneField, with: "5551111")

        app.buttons["Check Number"].tap()

        let stateTitle = app.descendants(matching: .any)["riskResult.stateTitle"]
        XCTAssertTrue(stateTitle.waitForExistence(timeout: 10))
        XCTAssertEqual(stateTitle.label, "Verified Caller")
        XCTAssertTrue(app.descendants(matching: .any)["riskResult.explanation"].waitForExistence(timeout: 5))

        XCTAssertFalse(app.buttons["Transfer to AI Protection"].exists)
        XCTAssertTrue(app.buttons["Return to Home"].waitForExistence(timeout: 5))
    }

    @MainActor
    func testSimulatedCallerStateProgression() throws {
        let app = XCUIApplication()
        app.launchEnvironment["FRAUS_USE_MOCK_VERIFICATION"] = "false"
        app.launchEnvironment["FRAUS_FALLBACK_TO_MOCK_VERIFICATION"] = "false"
        app.launchEnvironment["FRAUS_USE_MOCK_TAKEOVER"] = "false"
        app.launchEnvironment["FRAUS_FALLBACK_TO_MOCK_TAKEOVER"] = "true"
        app.launchEnvironment["FRAUS_BACKEND_BASE_URL"] = "http://127.0.0.1:8001"
        app.launch()

        XCTAssertTrue(app.buttons["Log In"].waitForExistence(timeout: 8))
        app.buttons["Log In"].tap()

        XCTAssertTrue(app.buttons["Continue"].waitForExistence(timeout: 8))
        app.buttons["Continue"].tap()

        let answerButton = app.buttons["Answer in Fraus"].firstMatch
        XCTAssertTrue(answerButton.waitForExistence(timeout: 8))
        answerButton.tap()

        XCTAssertTrue(app.buttons["Check Number"].waitForExistence(timeout: 8))
        app.buttons["Check Number"].tap()

        XCTAssertTrue(app.buttons["Transfer to AI Protection"].waitForExistence(timeout: 15))
        app.buttons["Transfer to AI Protection"].tap()

        XCTAssertTrue(app.buttons["Start AI Protection"].waitForExistence(timeout: 8))
        app.buttons["Start AI Protection"].tap()

        XCTAssertTrue(app.buttons["End Session"].waitForExistence(timeout: 15))

        let expectedBadges = ["AI Prepared", "AI Connecting", "AI Live", "AI Simulated Caller", "AI Agent Events", "AI Fallback"]
        var observedBadges: [String] = []

        let start = Date()
        while Date().timeIntervalSince(start) < 35 {
            for badge in expectedBadges {
                if app.staticTexts[badge].exists,
                   !observedBadges.contains(badge) {
                    observedBadges.append(badge)
                }
            }

            if observedBadges.contains("AI Agent Events") || observedBadges.contains("AI Fallback") {
                break
            }

            RunLoop.current.run(until: Date().addingTimeInterval(0.25))
        }

        let observedSummary = observedBadges.joined(separator: " -> ")
        let attachment = XCTAttachment(string: observedSummary)
        attachment.name = "ObservedConnectionStates"
        attachment.lifetime = .keepAlways
        add(attachment)

        XCTAssertTrue(
            observedBadges.contains("AI Connecting") || observedBadges.contains("AI Prepared"),
            "Expected startup state before live/fallback. Observed: \(observedSummary)"
        )

        XCTAssertTrue(
            observedBadges.contains("AI Agent Events") || observedBadges.contains("AI Fallback"),
            "Expected terminal demo state (agent events or fallback). Observed: \(observedSummary)"
        )

        if let preparedIndex = observedBadges.firstIndex(of: "AI Prepared"),
           let connectingIndex = observedBadges.firstIndex(of: "AI Connecting") {
            XCTAssertLessThanOrEqual(preparedIndex, connectingIndex)
        }
    }

    @MainActor
    func testActiveProtectionConversationTimelineAndAccessibilityIDs() throws {
        let app = XCUIApplication()
        app.launchEnvironment["FRAUS_USE_MOCK_VERIFICATION"] = "false"
        app.launchEnvironment["FRAUS_FALLBACK_TO_MOCK_VERIFICATION"] = "false"
        app.launchEnvironment["FRAUS_USE_MOCK_TAKEOVER"] = "false"
        app.launchEnvironment["FRAUS_FALLBACK_TO_MOCK_TAKEOVER"] = "false"
        app.launchEnvironment["FRAUS_BACKEND_BASE_URL"] = "http://127.0.0.1:8001"
        app.launch()

        XCTAssertTrue(app.buttons["Log In"].waitForExistence(timeout: 8))
        app.buttons["Log In"].tap()

        XCTAssertTrue(app.buttons["Continue"].waitForExistence(timeout: 8))
        app.buttons["Continue"].tap()

        let answerButton = app.buttons["Answer in Fraus"].firstMatch
        XCTAssertTrue(answerButton.waitForExistence(timeout: 8))
        answerButton.tap()

        XCTAssertTrue(app.buttons["Check Number"].waitForExistence(timeout: 8))
        app.buttons["Check Number"].tap()

        XCTAssertTrue(app.buttons["Transfer to AI Protection"].waitForExistence(timeout: 15))
        app.buttons["Transfer to AI Protection"].tap()

        XCTAssertTrue(app.buttons["Start AI Protection"].waitForExistence(timeout: 8))
        app.buttons["Start AI Protection"].tap()

        let timeline = app.descendants(matching: .any)["activeProtection.timeline.container"]
        XCTAssertTrue(timeline.waitForExistence(timeout: 15))

        XCTAssertTrue(app.descendants(matching: .any)["activeProtection.stateBadge"].waitForExistence(timeout: 8))
        XCTAssertTrue(app.descendants(matching: .any)["activeProtection.indicators.section"].waitForExistence(timeout: 8))
        XCTAssertTrue(app.descendants(matching: .any)["activeProtection.entities.section"].waitForExistence(timeout: 8))
        XCTAssertTrue(app.descendants(matching: .any)["activeProtection.handoff.section"].waitForExistence(timeout: 8))

        let callerMessages = app.descendants(matching: .any).matching(NSPredicate(format: "identifier BEGINSWITH %@", "activeProtection.timeline.callerMessage."))
        let aiMessages = app.descendants(matching: .any).matching(NSPredicate(format: "identifier BEGINSWITH %@", "activeProtection.timeline.aiMessage."))

        let start = Date()
        while Date().timeIntervalSince(start) < 30 {
            if callerMessages.count > 0 && aiMessages.count > 0 {
                break
            }
            RunLoop.current.run(until: Date().addingTimeInterval(0.25))
        }

        XCTAssertGreaterThan(callerMessages.count, 0, "Expected at least one caller message bubble")

        if aiMessages.count == 0 {
            let fallbackBadge = app.staticTexts["AI Fallback"]
            let retryButton = app.buttons["activeProtection.retryLiveConnection"]
            let modeLabel = app.descendants(matching: .any)["activeProtection.modeLabel"]

            XCTAssertTrue(
                fallbackBadge.exists || retryButton.exists || modeLabel.exists,
                "Expected AI message bubble, or explicit degraded/fallback UI indicators"
            )
        } else {
            XCTAssertGreaterThan(aiMessages.count, 0, "Expected at least one AI message bubble")
        }
    }

    private func digitsOnly(_ text: String) -> String {
        text.filter(\.isNumber)
    }

    private func waitForStaticTextDigitsMatch(in app: XCUIApplication, expectedDigits: String, timeout: TimeInterval) -> Bool {
        let start = Date()
        while Date().timeIntervalSince(start) < timeout {
            if app.staticTexts.allElementsBoundByIndex.contains(where: { digitsOnly($0.label) == expectedDigits }) {
                return true
            }
            RunLoop.current.run(until: Date().addingTimeInterval(0.2))
        }
        return false
    }

    private func replaceText(in textField: XCUIElement, with value: String) {
        textField.tap()
        if let current = textField.value as? String,
           !current.isEmpty,
           current != value {
            let deleteString = String(repeating: XCUIKeyboardKey.delete.rawValue, count: current.count)
            textField.typeText(deleteString)
        }
        textField.typeText(value)
    }

    @MainActor
    func testLaunchPerformance() throws {
        // This measures how long it takes to launch your application.
        measure(metrics: [XCTApplicationLaunchMetric()]) {
            XCUIApplication().launch()
        }
    }
}
