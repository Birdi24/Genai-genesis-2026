import Foundation

protocol TakeoverSessionServicing {
    func startTakeover(
        verificationResult: VerificationResult,
        demoCallSession: DemoCallSession?
    ) async throws -> ProtectionSession

    func fetchSession(
        sessionID: String,
        callCategory: DemoCallCategory?,
        sourceCallSessionID: UUID?,
        sessionStartTime: Date,
        fallbackSession: ProtectionSession?
    ) async throws -> ProtectionSession

    func ingestEvent(
        sessionID: String,
        payload: TakeoverSessionEventRequestPayload
    ) async throws
}

struct TakeoverSessionAPIConfiguration {
    let baseURL: URL
    let useMockMode: Bool
    let fallbackToMockOnFailure: Bool

    static let `default` = TakeoverSessionAPIConfiguration(
        baseURL: AppRuntimeConfiguration.verificationBaseURL,
        useMockMode: AppRuntimeConfiguration.useMockTakeoverMode,
        fallbackToMockOnFailure: AppRuntimeConfiguration.fallbackToMockOnTakeoverFailure
    )
}

enum TakeoverSessionAPIError: LocalizedError {
    case invalidResponse
    case networkUnavailable
    case serverError(code: Int)
    case decodingFailure
    case missingSessionID

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from takeover service."
        case .networkUnavailable:
            return "Cannot reach takeover backend right now."
        case .serverError(let code):
            return "Takeover service failed with status code \(code)."
        case .decodingFailure:
            return "Could not parse takeover session response."
        case .missingSessionID:
            return "Takeover service did not return a session ID."
        }
    }
}

final class TakeoverSessionService: TakeoverSessionServicing {
    private let configuration: TakeoverSessionAPIConfiguration
    private let session: URLSession
    private let mockFactory = MockProtectionSessionFactory()

    init(
        configuration: TakeoverSessionAPIConfiguration = .default,
        session: URLSession = .shared
    ) {
        self.configuration = configuration
        self.session = session
    }

    func startTakeover(
        verificationResult: VerificationResult,
        demoCallSession: DemoCallSession?
    ) async throws -> ProtectionSession {
        if configuration.useMockMode {
            return mockFactory.makeSession(
                for: verificationResult,
                callSession: demoCallSession
            )
        }

        do {
            let request = StartTakeoverRequest(
                phoneNumber: verificationResult.phoneNumber,
                callerLabel: demoCallSession?.callerLabel,
                riskLevel: verificationResult.riskLevel
            )

            let response = try await postStartTakeover(request)
            guard !response.sessionID.isEmpty else {
                throw TakeoverSessionAPIError.missingSessionID
            }

            return response.toProtectionSession(
                callCategory: demoCallSession?.callCategory,
                sourceCallSessionID: demoCallSession?.id,
                sessionStartTime: demoCallSession?.startTime ?? Date(),
                fallbackSession: nil
            )
        } catch {
            if configuration.fallbackToMockOnFailure {
                return mockFactory.makeSession(
                    for: verificationResult,
                    callSession: demoCallSession
                )
            }
            throw error
        }
    }

    func fetchSession(
        sessionID: String,
        callCategory: DemoCallCategory?,
        sourceCallSessionID: UUID?,
        sessionStartTime: Date,
        fallbackSession: ProtectionSession? = nil
    ) async throws -> ProtectionSession {
        if configuration.useMockMode {
            throw TakeoverSessionAPIError.networkUnavailable
        }

        let response = try await getSession(sessionID: sessionID)
        return response.toProtectionSession(
            callCategory: callCategory,
            sourceCallSessionID: sourceCallSessionID,
            sessionStartTime: sessionStartTime,
            fallbackSession: fallbackSession
        )
    }

    func ingestEvent(
        sessionID: String,
        payload: TakeoverSessionEventRequestPayload
    ) async throws {
        if configuration.useMockMode {
            return
        }

        let endpoint = configuration.baseURL
            .appendingPathComponent("session")
            .appendingPathComponent(sessionID)
            .appendingPathComponent("events")

        var urlRequest = URLRequest(url: endpoint)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try JSONEncoder().encode(payload)
        urlRequest.timeoutInterval = 8

        let (_, response): (Data, URLResponse)
        do {
            (_, response) = try await session.data(for: urlRequest)
        } catch {
            throw TakeoverSessionAPIError.networkUnavailable
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw TakeoverSessionAPIError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw TakeoverSessionAPIError.serverError(code: httpResponse.statusCode)
        }
    }

    private func postStartTakeover(_ request: StartTakeoverRequest) async throws -> TakeoverSessionResponse {
        let endpoint = configuration.baseURL.appendingPathComponent("start-takeover")
        var urlRequest = URLRequest(url: endpoint)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try JSONEncoder().encode(request)
        urlRequest.timeoutInterval = 12

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: urlRequest)
        } catch {
            throw TakeoverSessionAPIError.networkUnavailable
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw TakeoverSessionAPIError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw TakeoverSessionAPIError.serverError(code: httpResponse.statusCode)
        }

        do {
            return try JSONDecoder().decode(TakeoverSessionResponse.self, from: data)
        } catch {
            throw TakeoverSessionAPIError.decodingFailure
        }
    }

    private func getSession(sessionID: String) async throws -> TakeoverSessionResponse {
        let endpoint = configuration.baseURL
            .appendingPathComponent("session")
            .appendingPathComponent(sessionID)

        var urlRequest = URLRequest(url: endpoint)
        urlRequest.httpMethod = "GET"
        urlRequest.timeoutInterval = 12

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: urlRequest)
        } catch {
            throw TakeoverSessionAPIError.networkUnavailable
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw TakeoverSessionAPIError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw TakeoverSessionAPIError.serverError(code: httpResponse.statusCode)
        }

        do {
            return try JSONDecoder().decode(TakeoverSessionResponse.self, from: data)
        } catch {
            throw TakeoverSessionAPIError.decodingFailure
        }
    }
}
