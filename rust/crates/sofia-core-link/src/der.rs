//! Bounded DER walking that yields the subjectPublicKeyInfo bytes of one
//! X.509 certificate. Unknown or oversized structures fail closed; the
//! output is only ever hashed for the enrolled host public-key pin
//! comparison, never used to make trust claims by itself.

use sha2::{Digest, Sha256};

const MAX_CERTIFICATE_BYTES: usize = 16 * 1024;

struct Cursor<'a> {
    bytes: &'a [u8],
}

impl<'a> Cursor<'a> {
    fn new(bytes: &'a [u8]) -> Option<Self> {
        if bytes.len() > MAX_CERTIFICATE_BYTES {
            None
        } else {
            Some(Self { bytes })
        }
    }

    fn read_byte(&mut self) -> Option<u8> {
        let (first, rest) = self.bytes.split_first()?;
        self.bytes = rest;
        Some(*first)
    }

    fn read_length(&mut self) -> Option<usize> {
        let first = self.read_byte()?;
        if first < 0x80 {
            return Some(usize::from(first));
        }
        let count = usize::from(first & 0x7f);
        if count == 0 || count > 3 {
            return None;
        }
        let mut length: usize = 0;
        for _ in 0..count {
            length = length
                .checked_mul(256)?
                .checked_add(usize::from(self.read_byte()?))?;
        }
        if length > MAX_CERTIFICATE_BYTES {
            return None;
        }
        Some(length)
    }

    /// One definite-length tag-length-value: returns the exact content bytes.
    fn tagged(&mut self, tag: u8) -> Option<&'a [u8]> {
        if self.read_byte()? != tag {
            return None;
        }
        let length = self.read_length()?;
        let content = self.bytes.get(..length)?;
        self.bytes = self.bytes.get(length..)?;
        Some(content)
    }
}

/// The SHA-256 digest over the DER-encoded subjectPublicKeyInfo of one
/// X.509 certificate, byte-for-byte identical to the Python binding's
/// `sha256(public key DER SubjectPublicKeyInfo).hexdigest()`.
#[must_use]
pub fn spki_sha256(certificate: &[u8]) -> Option<[u8; 32]> {
    let mut whole = Cursor::new(certificate)?;
    let certificate = whole.tagged(0x30)?;
    let tbs = Cursor::new(certificate)?.tagged(0x30)?;

    // TBSCertificate ::= SEQUENCE { version [0] EXPLICIT Version OPTIONAL,
    // serialNumber INTEGER, signature AlgorithmIdentifier, issuer Name,
    // validity Validity, subject Name, subjectPublicKeyInfo, extensions
    // [3] EXPLICIT Extensions OPTIONAL }
    let mut parser = Cursor::new(tbs)?;
    if parser.bytes.first() == Some(&0xa0) {
        parser.tagged(0xa0)?;
    }
    let serial = parser.tagged(0x02)?;
    if serial.is_empty() {
        return None;
    }
    let _signature = parser.tagged(0x30)?;
    let _issuer = parser.tagged(0x30)?;
    let _validity = parser.tagged(0x30)?;
    let _subject = parser.tagged(0x30)?;
    let spki = parser.tagged(0x30)?;
    if spki.len() < 15 {
        return None;
    }
    // The Python binding hashes the full DER-encoded subjectPublicKeyInfo,
    // including its own tag and length. Re-encode canonically so the digest
    // matches for certificates with canonical length encodings (required of
    // any parseable X.509 certificate).
    let mut spki_der = Vec::with_capacity(spki.len() + 5);
    spki_der.push(0x30);
    let length = spki.len();
    if length < usize::from(u8::MAX) {
        spki_der.push(u8::try_from(length).expect("canonical single byte length"));
    } else if length <= 0xff_ff {
        spki_der.push(0x82);
        spki_der.push(u8::try_from(length >> 8).expect("bounded high length byte"));
        spki_der.push(u8::try_from(length & 0xff).expect("bounded low length byte"));
    } else {
        return None;
    }
    spki_der.extend_from_slice(spki);
    let digest = Sha256::digest(&spki_der);
    Some(digest.into())
}

#[cfg(test)]
mod tests {
    use super::{spki_sha256, MAX_CERTIFICATE_BYTES};
    use sha2::{Digest, Sha256};

    fn span(tag: u8, body: &[u8]) -> Vec<u8> {
        let mut out = vec![tag];
        let length = body.len();
        if length < usize::from(u8::MAX) {
            out.push(u8::try_from(length).expect("bounded length"));
        } else if length <= 0xff_ff {
            out.push(0x82);
            out.push(u8::try_from(length >> 8).expect("bounded high byte"));
            out.push(u8::try_from(length & 0xff).expect("bounded low byte"));
        } else {
            panic!("test fixtures must stay short");
        }
        out.extend_from_slice(body);
        out
    }

    #[test]
    fn digest_matches_independent_spki_hash() {
        let algorithm = span(
            0x30,
            &[
                0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01,
                0x01,
            ],
        );
        let key = span(0x03, &[vec![0u8; 256], vec![0x55_u8; 256]].concat());
        let spki_body = {
            let mut body = algorithm.clone();
            body.extend_from_slice(&key);
            body
        };
        let spki = span(0x30, &spki_body);
        let tbs_body = {
            let mut body = span(0xa0, &span(0x02, &[0x02]));
            body.extend_from_slice(&span(0x02, &[0x7f]));
            body.extend_from_slice(&span(0x30, &algorithm));
            body.extend_from_slice(&span(0x30, &span(0x63, &[0x50])));
            body.extend_from_slice(&span(0x30, &span(0x17, &[0x01])));
            body.extend_from_slice(&span(0x30, &span(0x5c, &[0x61])));
            body.extend_from_slice(&spki);
            body
        };
        let certificate = span(0x30, &span(0x30, &tbs_body));
        assert_eq!(
            spki_sha256(&certificate),
            Some(Sha256::digest(&spki).into()),
        );
    }

    #[test]
    fn wrong_tag_empty_and_oversized_certificates_fail_closed() {
        let algorithm = span(
            0x30,
            &[0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01, 0x01],
        );
        let spki = span(0x30, &algorithm);
        let tbs = span(0x30, &{
            let mut body = span(0xa0, &span(0x02, &[0x02]));
            body.extend_from_slice(&span(0x02, &[0x7f]));
            body.extend_from_slice(&span(0x30, &algorithm));
            body.extend_from_slice(&spki);
            body
        });

        let wrong_tbs_tag = span(0x31, &tbs);
        assert!(spki_sha256(&span(0x30, &wrong_tbs_tag)).is_none());

        let empty = [];
        assert!(spki_sha256(&empty).is_none());
        assert!(spki_sha256(&[0x30, 0x00]).is_none());

        let oversized = vec![0x30_u8; MAX_CERTIFICATE_BYTES + 1];
        assert!(spki_sha256(&oversized).is_none());
    }
}
