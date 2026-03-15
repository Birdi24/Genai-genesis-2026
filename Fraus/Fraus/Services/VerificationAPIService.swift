import Foundation

protocol VerificationServicing {
    func verifyNumber(_ request: VerifyNumberRequest) async throws -> VerifyNumberResponse
}

struct VerificationAPIConfiguration {
    let baseURL: URL
    let useMockMode: Bool
    let fallbackToMockOnFailure: Bool

    static let `default` = VerificationAPIConfiguration(
        baseURL: AppRuntimeConfiguration.verificationBaseURL,
        useMockMode: AppRuntimeConfiguration.useMockVerificationMode,
        fallbackToMockOnFailure: AppRuntimeConfiguration.fallbackToMockOnVerificationFailure
    )
}

enum VerificationAPIError: LocalizedError {
    case invalidURL
    case invalidResponse
    case networkUnavailable
    case serverError(code: Int)
    case decodingFailure
    case emptyPhoneNumber

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Verification service URL is invalid."
        case .invalidResponse:
            return "Invalid response from verification service."
        case .networkUnavailable:
            return "Cannot reach verification backend right now."
        case .serverError(let code):
            return "Verification service failed with status code \(code)."
        case .decodingFailure:
            return "Could not parse verification response."
        case .emptyPhoneNumber:
            return "Please enter a phone number."
        }
    }
}

final class VerificationAPIService: VerificationServicing {
    private let configuration: VerificationAPIConfiguration
    private let session: URLSession
    private let mockVerifier = MockVerificationService()

    init(
        configuration: VerificationAPIConfiguration = .default,
        session: URLSession = .shared
    ) {
        self.configuration = configuration
        self.session = session
    }

    func verifyNumber(_ request: VerifyNumberRequest) async throws -> VerifyNumberResponse {
        let number = request.phoneNumber.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !number.isEmpty else {
            throw VerificationAPIError.emptyPhoneNumber
        }

        if configuration.useMockMode {
            return mockResponse(for: number)
        }

        do {
            return try await callVerifyEndpoint(request: VerifyNumberRequest(phoneNumber: number))
        } catch {
            if configuration.fallbackToMockOnFailure {
                return mockResponse(for: number)
            }
            throw error
        }
    }

    private func callVerifyEndpoint(request: VerifyNumberRequest) async throws -> VerifyNumberResponse {
        let endpoint = configuration.baseURL.appendingPathComponent("verify-number")
        var urlRequest = URLRequest(url: endpoint)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try JSONEncoder().encode(request)
        urlRequest.timeoutInterval = 12

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: urlRequest)
        } catch {
            throw VerificationAPIError.networkUnavailable
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw VerificationAPIError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw VerificationAPIError.serverError(code: httpResponse.statusCode)
        }

        do {
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            return try decoder.decode(VerifyNumberResponse.self, from: data)
        } catch {
            throw VerificationAPIError.decodingFailure
        }
    }

    private func mockResponse(for phoneNumber: String) -> VerifyNumberResponse {
        let result = mockVerifier.verify(phoneNumber: phoneNumber)

        let status: VerifyBackendStatus
        switch result.state {
        case .verified:
            status = .verified
        case .suspicious:
            status = .scam
        case .unknown:
            status = .unknown
        }

        let derivedRisk: String
        switch result.state {
        case .verified:
            derivedRisk = "low"
        case .suspicious:
            derivedRisk = "high"
        case .unknown:
            derivedRisk = "medium"
        }

        return VerifyNumberResponse(
            phoneNumber: result.phoneNumber,
            status: status,
            reason: result.explanation,
            threatTags: result.threatTags.map(\.label),
            sourceLabel: "Fraus Verification Engine",
            riskLevel: derivedRisk
        )
    }
}
