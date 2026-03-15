import Foundation

enum AppRuntimeConfiguration {
    private static let environment = ProcessInfo.processInfo.environment

    static var verificationBaseURL: URL {
        if let configuredValue = environment["FRAUS_BACKEND_BASE_URL"],
           let configuredURL = URL(string: configuredValue),
           !configuredValue.isEmpty {
            return configuredURL
        }

        return URL(string: "http://127.0.0.1:8001")!
    }

    static var useMockVerificationMode: Bool {
        boolValue(for: "FRAUS_USE_MOCK_VERIFICATION", defaultValue: true)
    }

    static var fallbackToMockOnVerificationFailure: Bool {
        boolValue(for: "FRAUS_FALLBACK_TO_MOCK_VERIFICATION", defaultValue: true)
    }

    static var useMockTakeoverMode: Bool {
        boolValue(for: "FRAUS_USE_MOCK_TAKEOVER", defaultValue: false)
    }

    static var fallbackToMockOnTakeoverFailure: Bool {
        boolValue(for: "FRAUS_FALLBACK_TO_MOCK_TAKEOVER", defaultValue: true)
    }

    private static func boolValue(for key: String, defaultValue: Bool) -> Bool {
        guard let value = environment[key]?.lowercased() else {
            return defaultValue
        }

        switch value {
        case "1", "true", "yes", "y", "on":
            return true
        case "0", "false", "no", "n", "off":
            return false
        default:
            return defaultValue
        }
    }
}
