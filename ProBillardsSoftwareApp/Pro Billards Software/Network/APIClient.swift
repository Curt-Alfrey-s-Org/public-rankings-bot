import Foundation

// MARK: - Login request/response (matches your backend)

struct LoginRequest: Encodable {
    let username: String
    let password: String
}

struct LoginResponse: Decodable {
    let success: Bool
    let token: String?
    let user: String?
    let role: String?
    let message: String?
}

// MARK: - Rankings (matches backend GET /api/v1/rankings/wpba-women)

struct RankingItem: Decodable {
    let player_name: String
    let rank: Int
    let points: Double?
    let country: String?
    let fargo_rating: Double?
    let fargo_robustness: Int?
    let license_number: String?
    let stops_played: Int?
    let date: String?

    enum CodingKeys: String, CodingKey {
        case player_name, name, rank, points, country, fargo_rating, fargo_robustness, license_number, stops_played, date
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        player_name = (try? c.decode(String.self, forKey: .player_name)) ?? (try? c.decode(String.self, forKey: .name)) ?? ""
        rank = try c.decode(Int.self, forKey: .rank)
        points = try c.decodeIfPresent(Double.self, forKey: .points)
        country = try c.decodeIfPresent(String.self, forKey: .country)
        fargo_rating = try c.decodeIfPresent(Double.self, forKey: .fargo_rating)
        fargo_robustness = try c.decodeIfPresent(Int.self, forKey: .fargo_robustness)
        license_number = try c.decodeIfPresent(String.self, forKey: .license_number)
        stops_played = try c.decodeIfPresent(Int.self, forKey: .stops_played)
        date = try c.decodeIfPresent(String.self, forKey: .date)
    }
}

struct RankingsResponse: Decodable {
    let total: Int
    let count: Int
    let rankings: [RankingItem]
    let association: String?
}

// MARK: - API Client

enum APIClient {
    /// Build full URL for a path (path should start with / e.g. "/api/v1/auth/login").
    private static func url(for path: String) -> URL? {
        let base = Config.apiBaseURL.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let path = path.hasPrefix("/") ? path : "/" + path
        return URL(string: base + path)
    }

    /// POST /api/v1/auth/login — returns token and user info on success.
    static func login(username: String, password: String) async throws -> (token: String, user: String, role: String) {
        guard let url = url(for: "/api/v1/auth/login") else {
            throw URLError(.badURL)
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(LoginRequest(username: username, password: password))

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw URLError(.unknown) }
        let decoded = try JSONDecoder().decode(LoginResponse.self, from: data)

        if !decoded.success, let msg = decoded.message {
            throw NSError(domain: "APIClient", code: http.statusCode, userInfo: [NSLocalizedDescriptionKey: msg])
        }
        guard let token = decoded.token, let user = decoded.user, let role = decoded.role else {
            throw NSError(domain: "APIClient", code: 0, userInfo: [NSLocalizedDescriptionKey: "Invalid login response"])
        }
        return (token, user, role)
    }

    /// Perform a request with Bearer token (for authenticated endpoints).
    static func request(path: String, method: String = "GET", body: Data? = nil) async throws -> Data {
        guard let url = url(for: path) else { throw URLError(.badURL) }
        guard let token = KeychainHelper.loadToken() else {
            throw NSError(domain: "APIClient", code: 401, userInfo: [NSLocalizedDescriptionKey: "Not logged in"])
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = body

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw URLError(.unknown) }
        if http.statusCode == 401 {
            KeychainHelper.deleteToken()
            throw NSError(domain: "APIClient", code: 401, userInfo: [NSLocalizedDescriptionKey: "Session expired"])
        }
        if http.statusCode < 200 || http.statusCode >= 300 {
            let detail = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String
            let message = detail ?? "Request failed (\(http.statusCode))"
            throw NSError(domain: "APIClient", code: http.statusCode, userInfo: [NSLocalizedDescriptionKey: message])
        }
        return data
    }

    /// GET /api/v1/rankings by system. Use system id (e.g. "WPBA_Women", "WPA_Men", "WPA_Men_Yalin_8Ball").
    static func fetchRankings(system: String, limit: Int = 500, offset: Int = 0) async throws -> RankingsResponse {
        let encoded = system.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? system
        let path = "/api/v1/rankings/by-system/\(encoded)?limit=\(limit)&offset=\(offset)"
        let data = try await request(path: path)
        return try JSONDecoder().decode(RankingsResponse.self, from: data)
    }
}
//  APIClient.swift
//  Pro Billards Software
//
//  Created by Nickey Example on 3/11/26.
//

