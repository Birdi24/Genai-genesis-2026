import Foundation

enum MicrophoneAudioCaptureState: Equatable {
    case idle
    case requestingPermission
    case permissionDenied
    case capturing
    case stopped
    case failed
}

protocol MicrophoneAudioCapturing: AnyObject {
    var onStateChange: ((MicrophoneAudioCaptureState) -> Void)? { get set }

    func requestMicrophonePermission() async -> Bool
    func startCapture(onAudioChunk: @escaping (Data) -> Void) throws
    func stopCapture()
}

final class LiveMicrophoneAudioCaptureService: MicrophoneAudioCapturing {
    var onStateChange: ((MicrophoneAudioCaptureState) -> Void)?

    // Non-audio demo mode:
    // Fraus intentionally does not capture or stream microphone input.
    // This service remains as a disabled stub to preserve architecture boundaries.

    func requestMicrophonePermission() async -> Bool {
        onStateChange?(.permissionDenied)
        return false
    }

    func startCapture(onAudioChunk: @escaping (Data) -> Void) throws {
        onStateChange?(.failed)
        throw NSError(
            domain: "fraus.nonAudioDemo",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "Microphone capture is disabled for this demo mode."]
        )
    }

    func stopCapture() {
        onStateChange?(.stopped)
    }
}
