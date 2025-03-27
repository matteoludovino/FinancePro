package br.com.finance.FinancePro.financias.Transacoes.Model;
import jakarta.persistence.*;
import org.w3c.dom.Text;


@Entity
@Table(name = "tb_transações")
public class TransacaoModel {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;
    private String descItem;
    private float amount;
    private String type;

    public TransacaoModel() {
    }

    public TransacaoModel(String descItem, float amount, String type) {
        this.descItem = descItem;
        this.amount = amount;
        this.type = type;
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

    public String isType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }
}
