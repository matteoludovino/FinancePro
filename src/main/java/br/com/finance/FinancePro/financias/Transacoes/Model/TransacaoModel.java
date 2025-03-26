package br.com.finance.FinancePro.financias.Transacoes.Model;

import jakarta.persistence.*;

@Entity
@Table(name = "tb_valores")
public class TransacaoModel {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;
    private String descItem;
    private float amount;
    private String type;

    public TransacaoModel() {
    }

    public TransacaoModel(long id, String type, float amount, String descItem) {
        this.id = id;
        this.type = type;
        this.amount = amount;
        this.descItem = descItem;
    }

    public long getId() {
        return id;
    }

    public void setId(long id) {
        this.id = id;
    }

    public String getDescItem() {
        return descItem;
    }

    public void setDescItem(String descItem) {
        this.descItem = descItem;
    }

    public float getAmount() {
        return amount;
    }

    public void setAmount(float amount) {
        this.amount = amount;
    }

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }
}
