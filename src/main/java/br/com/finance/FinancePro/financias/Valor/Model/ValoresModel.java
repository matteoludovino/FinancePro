package br.com.finance.FinancePro.financias.Valor.Model;


import br.com.finance.FinancePro.financias.Transacoes.Model.TransacaoModel;
import jakarta.persistence.*;
import org.hibernate.annotations.DialectOverride;
import org.hibernate.annotations.JoinFormula;

import javax.xml.catalog.Catalog;
import java.util.List;


@Entity
@Table(name = "tb_valores")
public class ValoresModel {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;
    private float Entrada;
    private int Saida;
    private float ValorTot;

    public ValoresModel() {
    }

    public ValoresModel(float entrada, int saida, float valorTot) {
        Entrada = entrada;
        Saida = saida;
        ValorTot = valorTot;
    }

    public float getEntrada() {
        return Entrada;
    }

    public void setEntrada(float entrada) {
        Entrada = entrada;
    }

    public int getSaida() {
        return Saida;
    }

    public void setSaida(int saida) {
        Saida = saida;
    }

    public float getValorTot() {
        return ValorTot = this.Entrada - this.Saida;
    }
}