import XCTest
@testable import Fraus

final class ElevenLabsSocketEventParserTests: XCTestCase {
    func testParsesUserTranscript() {
        let events = ElevenLabsSocketEventParser.parse(object: [
            "type": "user_transcript",
            "user_transcript": "Caller asks for OTP",
            "event_id": "u1"
        ])

        XCTAssertEqual(events, [.userTranscript(text: "Caller asks for OTP", eventID: "u1")])
    }

    func testParsesAgentStreamingPart() {
        let events = ElevenLabsSocketEventParser.parse(object: [
            "type": "agent_chat_response_part",
            "agent_chat_response_part": "I can help",
            "event_id": "a_part_1"
        ])

        XCTAssertEqual(events, [.agentChatResponsePart(text: "I can help", responseID: "a_part_1")])
    }

    func testParsesAgentFinalResponse() {
        let events = ElevenLabsSocketEventParser.parse(object: [
            "type": "agent_response",
            "agent_response": "Please do not share the OTP.",
            "event_id": "a_final_1"
        ])

        XCTAssertEqual(events, [.agentResponse(text: "Please do not share the OTP.", eventID: "a_final_1")])
    }

    func testParsesAgentCorrection() {
        let events = ElevenLabsSocketEventParser.parse(object: [
            "type": "agent_response_correction",
            "agent_response_correction": "Do not share any verification code.",
            "corrected_event_id": "a_final_1"
        ])

        XCTAssertEqual(events, [.agentResponseCorrection(text: "Do not share any verification code.", correctedEventID: "a_final_1")])
    }

    func testParsesAudioEvent() {
        let events = ElevenLabsSocketEventParser.parse(object: [
            "type": "audio",
            "sequence": 7,
            "event_id": "audio_7"
        ])

        XCTAssertEqual(events, [.audio(sequence: 7, eventID: "audio_7")])
    }

    func testParsesPingAndPong() {
        let pingEvents = ElevenLabsSocketEventParser.parse(object: [
            "type": "ping",
            "event_id": "p1"
        ])
        let pongEvents = ElevenLabsSocketEventParser.parse(object: [
            "type": "pong",
            "event_id": "p1"
        ])

        XCTAssertEqual(pingEvents, [.ping(eventID: "p1")])
        XCTAssertEqual(pongEvents, [.pong(eventID: "p1")])
    }
}
