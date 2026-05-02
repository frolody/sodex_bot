package main

import (
	"encoding/json"
	"fmt"
)

type PerpsOrder struct {
	ClOrdID      string `json:"clOrdID"`
	Modifier     int    `json:"modifier"`
	Side         int    `json:"side"`
	OrderType    int    `json:"type"`
	TimeInForce  int    `json:"timeInForce"`
	Price        string `json:"price,omitempty"`
	Quantity     string `json:"quantity,omitempty"`
	Funds        string `json:"funds,omitempty"`
	StopPrice    string `json:"stopPrice,omitempty"`
	StopType     int    `json:"stopType,omitempty"`
	TriggerType  int    `json:"triggerType,omitempty"`
	ReduceOnly   bool   `json:"reduceOnly"`
	PositionSide int    `json:"positionSide"`
}

type NewOrderParams struct {
	AccountID int          `json:"accountID"`
	SymbolID  int          `json:"symbolID"`
	Orders    []PerpsOrder `json:"orders"`
}

func main() {
	item := PerpsOrder{
		ClOrdID:      "4739-1776343537809",
		Modifier:     1,
		Side:         1,
		OrderType:    1,
		TimeInForce:  1,
		Price:        "75074",
		Quantity:     "0.0002",
		ReduceOnly:   false,
		PositionSide: 1,
	}

	payload := NewOrderParams{
		AccountID: 4739,
		SymbolID:  1,
		Orders:    []PerpsOrder{item},
	}

	b, _ := json.Marshal(payload)
	fmt.Printf("HEX: %x\n", b)
	fmt.Printf("STR: %s\n", string(b))
}
