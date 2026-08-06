---
title: Capacity Blocks 실전 가이드
tags:
  - 의사결정
  - 비용
  - Capacity Blocks
---

# Capacity Blocks 실전 가이드

GPU/Trainium 클러스터를 단기간(1~14일) 확정 예약하는 **EC2 Capacity Blocks for ML** 사용법을 단계별로 안내합니다.

---

## 🎯 Capacity Blocks란?

| 항목 | 설명 |
|------|------|
| **목적** | ML 학습/추론을 위한 단기 GPU/Trainium 용량 확보 |
| **예약 기간** | 1일 ~ 14일 (시작일 지정) |
| **결제** | 예약 시 선불 (시작 전 취소 가능) |
| **지원 인스턴스** | p5.48xlarge, p5e.48xlarge, p5en.48xlarge, trn1.32xlarge, trn2.48xlarge 등 |
| **용량 보장** | 예약 확정 시 100% 보장 |

---

## 📋 사전 준비

### 1. 서비스 쿼터 확인

Capacity Blocks는 On-Demand 쿼터와 별도입니다. Service Quotas에서 확인:

```
서비스: Amazon EC2
쿼터 이름: Running Capacity Block P Hosts (또는 Trn)
```

!!! warning "쿼터가 0이면 예약 불가"
    신규 계정은 기본값 0일 수 있습니다. 쿼터 증가 요청 먼저 하세요.

### 2. 리전 선택

Capacity Blocks가 제공되는 리전에서만 사용 가능합니다:

| 인스턴스 | 주요 가용 리전 |
|---------|--------------|
| p5.48xlarge | us-east-1, us-east-2, us-west-2 |
| p5e.48xlarge | us-east-1, us-east-2, us-west-2 |
| p5en.48xlarge | us-east-1, us-west-2, ap-northeast-2 |
| trn1.32xlarge | us-east-1, us-east-2, us-west-2 |
| trn2.48xlarge | us-east-1, us-east-2, us-west-2, ap-northeast-2, sa-east-1, ap-southeast-4 |

!!! tip "최신 가용성은 콘솔에서 확인"
    리전/인스턴스별 가용 오퍼링은 수시로 변경됩니다.

### 3. IAM 권한

최소 필요 권한:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeCapacityBlockOfferings",
        "ec2:PurchaseCapacityBlock",
        "ec2:DescribeCapacityReservations",
        "ec2:CancelCapacityReservation",
        "ec2:RunInstances",
        "ec2:CreateCapacityReservationFleet"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## 🚀 Step-by-Step: 콘솔에서 예약하기

### Step 1: 오퍼링 조회

1. **EC2 콘솔** → 좌측 메뉴 → **Capacity Reservations** → **Capacity Blocks** 탭
2. **Find Capacity Blocks** 클릭
3. 필터 입력:
    - **Instance type**: 원하는 인스턴스 (예: `p5en.48xlarge`)
    - **Instance quantity**: 필요한 대수
    - **Duration**: 예약 기간 (예: 7일)
    - **Start date range**: 시작 가능 기간
4. **Search** 클릭 → 가용 오퍼링 목록 표시

### Step 2: 오퍼링 선택 & 구매

1. 원하는 오퍼링의 **Purchase** 버튼 클릭
2. 요약 확인:
    - 인스턴스 타입/수량
    - 시작~종료 일시 (UTC)
    - 총 비용
3. **Purchase capacity block** 클릭
4. 상태가 `payment-pending` → `active` (시작일)로 변경됨

### Step 3: 인스턴스 실행

예약 시작 시간 이후:

1. **EC2 콘솔** → **Launch Instance**
2. 인스턴스 타입: 예약한 타입 선택
3. **Advanced details** → **Capacity reservation**:
    - Capacity Reservation target: **Specific capacity reservation**
    - Capacity Reservation ID 선택
4. **Launch instance**

!!! info "예약 시간 = UTC 기준"
    한국 시간(KST)은 UTC+9입니다. 예: UTC 00:00 시작 = KST 09:00 시작

---

## 💻 CLI로 예약하기

### 오퍼링 조회

```bash
aws ec2 describe-capacity-block-offerings \
  --instance-type p5en.48xlarge \
  --instance-count 2 \
  --capacity-duration-hours 168 \
  --start-date-range "2026-08-10T00:00:00Z" \
  --end-date-range "2026-08-20T00:00:00Z" \
  --region ap-northeast-2
```

출력 예시:

```json
{
  "CapacityBlockOfferings": [
    {
      "CapacityBlockOfferingId": "cbro-0123456789abcdef0",
      "InstanceType": "p5en.48xlarge",
      "AvailabilityZone": "ap-northeast-2a",
      "InstanceCount": 2,
      "StartDate": "2026-08-11T00:00:00Z",
      "EndDate": "2026-08-18T00:00:00Z",
      "CapacityBlockDurationHours": 168,
      "UpfrontFee": "45000.00",
      "CurrencyCode": "USD"
    }
  ]
}
```

### 구매

```bash
aws ec2 purchase-capacity-block \
  --capacity-block-offering-id cbro-0123456789abcdef0 \
  --instance-platform Linux/UNIX \
  --region ap-northeast-2
```

### 인스턴스 실행

```bash
aws ec2 run-instances \
  --instance-type p5en.48xlarge \
  --capacity-reservation-specification \
    "CapacityReservationTarget={CapacityReservationId=cr-0123456789abcdef0}" \
  --image-id ami-xxxxxxxx \
  --count 2 \
  --region ap-northeast-2
```

---

## 📐 활용 패턴

### 패턴 1: 학습 스프린트

```
[Day 0] 오퍼링 조회 & 예약 (7일)
[Day 1] 인스턴스 Launch → 환경 세팅 (DLAMI, Docker, EFA)
[Day 2-6] 집중 학습 (체크포인트 S3 저장)
[Day 7] 학습 완료 → 인스턴스 종료 (자동 해제)
```

### 패턴 2: 워크숍/데모

```
[2주 전] 1~2일 오퍼링 예약
[당일] 인스턴스 Launch → 핸즈온 진행
[종료] 자동 해제 (추가 비용 없음)
```

### 패턴 3: 반복 예약 자동화

```python
import boto3
from datetime import datetime, timedelta

ec2 = boto3.client('ec2', region_name='ap-northeast-2')

# 매주 월요일 시작 7일 블록 자동 조회 & 구매
response = ec2.describe_capacity_block_offerings(
    InstanceType='trn2.48xlarge',
    InstanceCount=4,
    CapacityDurationHours=168,
    StartDateRange=datetime.utcnow() + timedelta(days=7),
    EndDateRange=datetime.utcnow() + timedelta(days=14),
)

offerings = response['CapacityBlockOfferings']
if offerings:
    best = min(offerings, key=lambda x: float(x['UpfrontFee']))
    ec2.purchase_capacity_block(
        CapacityBlockOfferingId=best['CapacityBlockOfferingId'],
        InstancePlatform='Linux/UNIX',
    )
    print(f"Reserved: {best['StartDate']} ~ {best['EndDate']}")
```

---

## ⚠️ 주의사항

| 항목 | 내용 |
|------|------|
| **취소** | 시작일 이전에만 가능 (시작 후 환불 불가) |
| **미사용** | 인스턴스를 안 띄워도 비용 발생 (선불 완료) |
| **종료** | 예약 종료 시 인스턴스 자동 종료됨 — 데이터 백업 필수 |
| **EBS** | 인스턴스 종료 시 EBS도 함께 삭제될 수 있음 (`DeleteOnTermination` 확인) |
| **시간대** | 모든 시간은 UTC 기준 |
| **쿼터** | CB 쿼터 ≠ On-Demand 쿼터 (별도 관리) |

---

## 🔍 모니터링 & 트러블슈팅

### 예약 상태 확인

```bash
aws ec2 describe-capacity-reservations \
  --filters "Name=instance-type,Values=p5en.48xlarge" \
  --region ap-northeast-2
```

상태값:

| 상태 | 의미 |
|------|------|
| `payment-pending` | 결제 처리 중 |
| `payment-failed` | 결제 실패 (카드/한도 확인) |
| `scheduled` | 예약 확정, 시작 대기 |
| `active` | 현재 사용 가능 |
| `expired` | 기간 만료 |
| `cancelled` | 사용자 취소 |

### 오퍼링이 안 보일 때

1. **리전 확인** — 해당 인스턴스가 CB 지원되는 리전인지
2. **쿼터 확인** — CB 쿼터가 0이면 오퍼링 자체가 안 보임
3. **수량** — 너무 큰 수량 요청 시 매칭 안 될 수 있음 (줄여서 재시도)
4. **기간** — 1~14일 범위만 지원

---

## 📚 참고 자료

- [Capacity Blocks for ML 공식 문서](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-capacity-blocks.html)
- [EC2 Capacity Blocks 요금](https://aws.amazon.com/ec2/pricing/capacity-blocks/)
- [Capacity Blocks FAQ](https://aws.amazon.com/ec2/faqs/#Capacity_Blocks_for_ML)
- [XC 구매 옵션 비교](purchase-options/index.md)
